"""Hermes tools for persisting and running farm data pipelines."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

from openpasture.domain import DataPipeline
from openpasture.ingestion import DataPipelineRunner
from openpasture.runtime import get_skills_dir, get_store, resolve_farm_id, set_active_farm_id
from openpasture.tools._common import (
    json_response,
    make_id,
    optional_bool,
    optional_str,
    optional_str_list,
    require_str,
)

SAVE_DATA_PIPELINE_SCHEMA = {
    "type": "object",
    "description": (
        "Persist a farm data pipeline after the conversational setup work is already done. "
        "Use this only after exploring the site with Firecrawl CLI and deciding what to collect."
    ),
    "properties": {
        "farm_id": {"type": "string"},
        "vendor": {"type": "string"},
        "service": {"type": "string"},
        "login_url": {"type": "string"},
        "profile_id": {"type": "string"},
        "pipeline_id": {"type": "string"},
        "pipeline_name": {"type": "string"},
        "collection_goal": {"type": "string"},
        "target_urls": {"type": "array", "items": {"type": "string"}},
        "extraction_prompts": {"type": "array", "items": {"type": "string"}},
        "observation_source": {"type": "string"},
        "observation_tags": {"type": "array", "items": {"type": "string"}},
        "schedule": {"type": "string"},
        "login_flow_notes": {"type": "string"},
        "navigation_notes": {"type": "array", "items": {"type": "string"}},
        "output_shape": {"type": "string"},
        "known_gotchas": {"type": "array", "items": {"type": "string"}},
        "enable": {"type": "boolean"},
        "verify_now": {"type": "boolean"},
    },
    "required": ["login_url", "target_urls", "extraction_prompts"],
    "additionalProperties": True,
}

RUN_DATA_PIPELINE_SCHEMA = {
    "type": "object",
    "description": "Run one configured farm data pipeline immediately.",
    "properties": {
        "pipeline_id": {"type": "string"},
    },
    "required": ["pipeline_id"],
    "additionalProperties": True,
}

LIST_DATA_PIPELINES_SCHEMA = {
    "type": "object",
    "description": "List configured farm data pipelines. farm_id is optional when one farm is active.",
    "properties": {
        "farm_id": {"type": "string"},
    },
    "additionalProperties": True,
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "pipeline"


def _infer_vendor(args: dict[str, object], *, login_url: str) -> str:
    for key in ("vendor", "service", "name"):
        value = optional_str(args, key)
        if value:
            return value

    hostname = urlparse(login_url).hostname or ""
    host_parts = [part for part in hostname.split(".") if part]
    if len(host_parts) >= 2:
        return host_parts[-2]
    if host_parts:
        return host_parts[0]
    raise ValueError("'vendor' is required or must be inferable from 'login_url'.")


def _render_vendor_skill(
    *,
    vendor: str,
    vendor_slug: str,
    login_url: str,
    collection_goal: str | None,
    extraction_prompts: list[str],
    login_flow_notes: str | None,
    navigation_notes: list[str],
    output_shape: str | None,
    known_gotchas: list[str],
) -> str:
    output_shape_text = output_shape or (
        "Return JSON objects with observed_at, content, metrics, and optional tags/media_url."
    )
    lines = [
        "---",
        f"name: pipeline-{vendor_slug}",
        (
            "description: Collect recurring farm observations from "
            f"{vendor} using an authenticated Firecrawl profile and the learned site navigation."
        ),
        "version: 1.0.0",
        "---",
        f"# Pipeline {vendor}",
        "",
        "## Login",
        "",
        f"- Login URL: `{login_url}`",
        f"- Expected authentication flow: `{login_flow_notes or 'Farmer logs in manually through the Firecrawl live handoff.'}`",
        "",
        "## Navigation",
        "",
    ]
    if navigation_notes:
        lines.extend(f"- {note}" for note in navigation_notes)
    else:
        lines.append("- Resume the authenticated profile and navigate to the data pages needed for collection.")
    lines.extend(
        [
            "",
            "## Extraction Prompts",
            "",
            *[f"- `{prompt}`" for prompt in extraction_prompts],
            "",
            "## Output Shape",
            "",
            f"- {output_shape_text}",
            "",
            "## Collection Goal",
            "",
            f"- {collection_goal or 'Collect the configured daily farm signal.'}",
            "",
            "## Gotchas",
            "",
        ]
    )
    if known_gotchas:
        lines.extend(f"- {item}" for item in known_gotchas)
    else:
        lines.append("- Avoid storing credentials or farm-specific secrets in this skill.")
    lines.append("")
    return "\n".join(lines)


def _write_vendor_skill(vendor_slug: str, skill_text: str) -> tuple[Path, str]:
    skill_dir = get_skills_dir() / f"pipeline-{vendor_slug}"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(skill_text)
    return skill_path, hashlib.sha256(skill_text.encode("utf-8")).hexdigest()


def handle_save_data_pipeline(args: dict[str, object]) -> str:
    farm_id = resolve_farm_id(args)
    login_url = optional_str(args, "login_url")
    if login_url is None:
        raise ValueError("'login_url' is required.")

    target_urls = optional_str_list(args, "target_urls")
    extraction_prompts = optional_str_list(args, "extraction_prompts")
    if not target_urls:
        raise ValueError("'target_urls' must contain at least one URL.")
    if not extraction_prompts:
        raise ValueError("'extraction_prompts' must contain at least one prompt.")

    vendor = _infer_vendor(args, login_url=login_url)
    vendor_slug = _slugify(vendor)
    profile_id = optional_str(args, "profile_id") or f"{vendor_slug}-{farm_id}"
    collection_goal = optional_str(args, "collection_goal")
    navigation_notes = optional_str_list(args, "navigation_notes")
    known_gotchas = optional_str_list(args, "known_gotchas")

    skill_text = _render_vendor_skill(
        vendor=vendor,
        vendor_slug=vendor_slug,
        login_url=login_url,
        collection_goal=collection_goal,
        extraction_prompts=extraction_prompts,
        login_flow_notes=optional_str(args, "login_flow_notes"),
        navigation_notes=navigation_notes,
        output_shape=optional_str(args, "output_shape"),
        known_gotchas=known_gotchas,
    )
    skill_path, skill_hash = _write_vendor_skill(vendor_slug, skill_text)

    pipeline = DataPipeline(
        id=optional_str(args, "pipeline_id") or make_id("pipeline"),
        farm_id=farm_id,
        name=optional_str(args, "pipeline_name") or vendor_slug,
        profile_id=profile_id,
        login_url=login_url,
        target_urls=target_urls,
        extraction_prompts=extraction_prompts,
        observation_source=optional_str(args, "observation_source") or vendor_slug,
        observation_tags=optional_str_list(args, "observation_tags"),
        schedule=optional_str(args, "schedule") or "0 5 * * *",
        vendor_skill_version=f"sha256:{skill_hash}",
        enabled=bool(optional_bool(args, "enable")),
    )

    store = get_store()
    store.create_pipeline(pipeline)
    set_active_farm_id(farm_id)

    sample_observations: list[object] = []
    if optional_bool(args, "verify_now"):
        sample_observations = DataPipelineRunner(store).collect(pipeline.id)

    return json_response(
        status="ok",
        pipeline=pipeline,
        skill_path=str(skill_path),
        verified=bool(optional_bool(args, "verify_now")),
        sample_observations=sample_observations,
    )


def handle_run_data_pipeline(args: dict[str, object]) -> str:
    store = get_store()
    pipeline_id = require_str(args, "pipeline_id")
    observations = DataPipelineRunner(store).collect(pipeline_id)
    pipeline = store.get_pipeline(pipeline_id)
    pending_actions = store.list_pending_actions(pipeline.farm_id) if pipeline is not None else []
    if pipeline is not None:
        set_active_farm_id(pipeline.farm_id)
    return json_response(
        status="ok",
        pipeline=pipeline,
        observations=observations,
        observation_count=len(observations),
        pending_actions=pending_actions,
    )


def handle_list_data_pipelines(args: dict[str, object]) -> str:
    store = get_store()
    farm_id = resolve_farm_id(args)
    pipelines = store.list_pipelines(farm_id)
    set_active_farm_id(farm_id)
    return json_response(status="ok", farm_id=farm_id, count=len(pipelines), pipelines=pipelines)
