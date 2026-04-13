"""Generic observation pipeline for authenticated external farm systems."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable
from datetime import datetime
from logging import getLogger
from uuid import uuid4

from openpasture.domain import DataPipeline, FarmerAction, Observation, normalize_observation_source
from openpasture.store.protocol import FarmStore

logger = getLogger(__name__)

CommandRunner = Callable[[list[str]], str]

_AUTH_FAILURE_TOKENS = ("auth", "login", "unauthorized", "forbidden", "expired", "session")


def _firecrawl_env() -> dict[str, str]:
    env = dict(os.environ)
    if not env.get("FIRECRAWL_API_KEY"):
        return env

    stored_auth_env = dict(env)
    stored_auth_env.pop("FIRECRAWL_API_KEY", None)
    completed = subprocess.run(
        ["firecrawl", "--status"],
        check=False,
        capture_output=True,
        text=True,
        env=stored_auth_env,
    )
    if completed.returncode == 0 and "Authenticated" in completed.stdout:
        return stored_auth_env
    return env


def _run_command(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=_firecrawl_env(),
    )
    return completed.stdout.strip()


def _extract_json_payload(output: str) -> object:
    stripped = output.strip()
    if not stripped:
        return []

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.DOTALL)
    if fenced_match:
        return json.loads(fenced_match.group(1).strip())

    json_start = min((idx for idx in (stripped.find("["), stripped.find("{")) if idx != -1), default=-1)
    if json_start == -1:
        raise ValueError("Firecrawl interact output did not contain JSON.")
    return json.loads(stripped[json_start:])


def _parse_observed_at(value: object) -> datetime:
    if isinstance(value, str) and value.strip():
        return datetime.fromisoformat(value)
    return datetime.utcnow()


class DataPipelineRunner:
    """Collect observations for configured external data pipelines."""

    def __init__(self, store: FarmStore, command_runner: CommandRunner | None = None):
        self.store = store
        self.command_runner = command_runner or _run_command

    def collect(self, pipeline_id: str) -> list[Observation]:
        pipeline = self.store.get_pipeline(pipeline_id)
        if pipeline is None:
            raise ValueError(f"Pipeline '{pipeline_id}' does not exist.")
        return self.collect_pipeline(pipeline)

    def collect_pipeline(self, pipeline: DataPipeline) -> list[Observation]:
        if not pipeline.enabled:
            return []
        self._require_firecrawl_api_key()

        observations: list[Observation] = []
        try:
            for target_url in pipeline.target_urls:
                self._scrape(target_url, pipeline.profile_id)
                for prompt in pipeline.extraction_prompts:
                    payload = self._interact(prompt)
                    observations.extend(self._build_observations(payload, pipeline))
        except Exception as exc:
            message = str(exc)
            logger.warning("Pipeline '%s' collection failed: %s", pipeline.id, message)
            self.store.update_pipeline(pipeline.id, last_error=message)
            if self._looks_like_auth_failure(message):
                self._queue_reauth_action(pipeline)
            return []

        for observation in observations:
            self.store.record_observation(observation)
        self.store.update_pipeline(
            pipeline.id,
            last_collected_at=datetime.utcnow(),
            last_error=None,
        )
        return observations

    def _scrape(self, target_url: str, profile_id: str) -> None:
        self.command_runner(
            [
                "firecrawl",
                "scrape",
                target_url,
                "--profile",
                profile_id,
                "--no-save-changes",
            ]
        )

    def _interact(self, prompt: str) -> object:
        output = self.command_runner(["firecrawl", "interact", "--prompt", prompt])
        return _extract_json_payload(output)

    def _build_observations(self, payload: object, pipeline: DataPipeline) -> list[Observation]:
        if isinstance(payload, dict) and isinstance(payload.get("observations"), list):
            raw_observations = payload["observations"]
        elif isinstance(payload, list):
            raw_observations = payload
        elif isinstance(payload, dict):
            raw_observations = [payload]
        else:
            raise ValueError("Firecrawl interact output must be a JSON object or list.")

        observations: list[Observation] = []
        for raw_observation in raw_observations:
            if not isinstance(raw_observation, dict):
                raise ValueError("Each extracted observation must be a JSON object.")
            prompt_tags = raw_observation.get("tags", [])
            tags = list(dict.fromkeys([*pipeline.observation_tags, *(prompt_tags if isinstance(prompt_tags, list) else [])]))
            metrics = raw_observation.get("metrics", {})
            if not isinstance(metrics, dict):
                metrics = {"value": metrics}
            observations.append(
                Observation(
                    id=str(raw_observation.get("id") or f"{pipeline.name}_{uuid4().hex}"),
                    farm_id=pipeline.farm_id,
                    source=normalize_observation_source(pipeline.observation_source),
                    observed_at=_parse_observed_at(raw_observation.get("observed_at")),
                    content=str(raw_observation.get("content") or f"Imported from {pipeline.name}."),
                    paddock_id=self._optional_string(raw_observation.get("paddock_id")),
                    herd_id=self._optional_string(raw_observation.get("herd_id")),
                    metrics=metrics,
                    media_url=self._optional_string(raw_observation.get("media_url")),
                    tags=tags,
                )
            )
        return observations

    def _queue_reauth_action(self, pipeline: DataPipeline) -> None:
        pending_actions = self.store.list_pending_actions(pipeline.farm_id)
        for action in pending_actions:
            if action.action_type != "reauth":
                continue
            if action.context.get("pipeline_id") == pipeline.id:
                return

        action = FarmerAction(
            id=f"action_{uuid4().hex}",
            farm_id=pipeline.farm_id,
            action_type="reauth",
            summary=f"Reconnect {pipeline.name} so the data pipeline can resume.",
            context={
                "pipeline_id": pipeline.id,
                "profile_id": pipeline.profile_id,
                "login_url": pipeline.login_url,
            },
        )
        self.store.create_farmer_action(action)

    def _looks_like_auth_failure(self, message: str) -> bool:
        lowered = message.lower()
        return any(token in lowered for token in _AUTH_FAILURE_TOKENS)

    def _require_firecrawl_api_key(self) -> None:
        if os.environ.get("FIRECRAWL_API_KEY", "").strip():
            return
        completed = subprocess.run(
            ["firecrawl", "--status"],
            check=False,
            capture_output=True,
            text=True,
            env=_firecrawl_env(),
        )
        if completed.returncode == 0 and "Authenticated" in completed.stdout:
            return
        raise ValueError(
            "Data pipelines require an authenticated Firecrawl CLI session or FIRECRAWL_API_KEY."
        )

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value
        return None
