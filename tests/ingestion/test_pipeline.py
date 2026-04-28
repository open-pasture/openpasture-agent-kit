from __future__ import annotations

import json
from datetime import datetime

from openpasture.domain import DataPipeline, Farm
from openpasture.ingestion import DataPipelineRunner
from openpasture.store.sqlite import SQLiteStore


def build_store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / ".openpasture")
    store.bootstrap()
    return store


def test_data_pipeline_runner_collects_observations(tmp_path, monkeypatch):
    store = build_store(tmp_path)
    farm = Farm(id="farm_1", name="Willow Creek", timezone="America/Chicago")
    pipeline = DataPipeline(
        id="pipeline_1",
        farm_id=farm.id,
        name="nofence",
        profile_id="nofence-farm_1",
        login_url="https://app.nofence.no/login",
        target_urls=["https://app.nofence.no/dashboard"],
        extraction_prompts=["Extract today's alerts as observations."],
        observation_source="nofence",
        observation_tags=["integration"],
    )
    commands: list[list[str]] = []

    def fake_runner(command: list[str]) -> str:
        commands.append(command)
        if command[:2] == ["firecrawl", "scrape"]:
            return ""
        if command[:2] == ["firecrawl", "interact"]:
            return json.dumps(
                {
                    "observations": [
                        {
                            "observed_at": datetime.utcnow().isoformat(),
                            "content": "Two fence breach alerts overnight.",
                            "metrics": {"breach_count": 2},
                            "tags": ["alerts"],
                        }
                    ]
                }
            )
        raise AssertionError(f"Unexpected command: {command}")

    store.create_farm(farm)
    store.create_pipeline(pipeline)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")

    runner = DataPipelineRunner(store, command_runner=fake_runner)
    observations = runner.collect(pipeline.id)

    assert len(observations) == 1
    assert observations[0].source == "nofence"
    assert observations[0].tags == ["integration", "alerts"]
    assert commands[0] == [
        "firecrawl",
        "scrape",
        "https://app.nofence.no/dashboard",
        "--profile",
        "nofence-farm_1",
        "--no-save-changes",
    ]
    assert commands[1] == ["firecrawl", "interact", "--prompt", "Extract today's alerts as observations."]
    assert store.get_recent_observations(farm.id, days=7)[0].content == "Two fence breach alerts overnight."

    stored_pipeline = store.get_pipeline(pipeline.id)
    assert stored_pipeline is not None
    assert stored_pipeline.last_collected_at is not None
    assert stored_pipeline.last_error is None


def test_data_pipeline_runner_creates_reauth_action_on_auth_failure(tmp_path, monkeypatch):
    store = build_store(tmp_path)
    farm = Farm(id="farm_1", name="Willow Creek", timezone="America/Chicago")
    pipeline = DataPipeline(
        id="pipeline_1",
        farm_id=farm.id,
        name="nofence",
        profile_id="nofence-farm_1",
        login_url="https://app.nofence.no/login",
        target_urls=["https://app.nofence.no/dashboard"],
        extraction_prompts=["Extract today's alerts as observations."],
        observation_source="nofence",
    )

    def failing_runner(command: list[str]) -> str:
        if command[:2] == ["firecrawl", "scrape"]:
            return ""
        raise ValueError("Session expired. Login required.")

    store.create_farm(farm)
    store.create_pipeline(pipeline)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")

    runner = DataPipelineRunner(store, command_runner=failing_runner)

    assert runner.collect(pipeline.id) == []
    assert runner.collect(pipeline.id) == []

    pending_actions = store.list_pending_actions(farm.id)
    assert len(pending_actions) == 1
    assert pending_actions[0].action_type == "reauth"
    assert pending_actions[0].context["pipeline_id"] == pipeline.id

    stored_pipeline = store.get_pipeline(pipeline.id)
    assert stored_pipeline is not None
    assert stored_pipeline.last_error == "Session expired. Login required."
