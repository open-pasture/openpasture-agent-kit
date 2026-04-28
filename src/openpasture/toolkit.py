"""Framework-neutral openPasture tool catalog."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from openpasture.tools import brief, farm, knowledge, observe, onboarding, pipeline, plan

ToolHandler = Callable[[dict[str, object]], str]


@dataclass(frozen=True)
class ToolSpec:
    """A portable executable capability exposed by openPasture."""

    name: str
    schema: dict[str, Any]
    handler: ToolHandler
    description: str
    tags: tuple[str, ...] = ()
    emoji: str | None = None
    related_skills: tuple[str, ...] = ()


TOOLSET = "openpasture"

TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="save_data_pipeline",
        schema=pipeline.SAVE_DATA_PIPELINE_SCHEMA,
        handler=pipeline.handle_save_data_pipeline,
        description=(
            "Persist a learned data pipeline and write the reusable vendor skill after "
            "a Firecrawl-guided setup conversation."
        ),
        tags=("pipeline", "ingestion", "automation"),
        emoji="🔌",
        related_skills=("data-pipeline-setup",),
    ),
    ToolSpec(
        name="run_data_pipeline",
        schema=pipeline.RUN_DATA_PIPELINE_SCHEMA,
        handler=pipeline.handle_run_data_pipeline,
        description="Run one configured data pipeline immediately and return the collected observations.",
        tags=("pipeline", "ingestion"),
        emoji="📡",
        related_skills=("data-pipeline-setup",),
    ),
    ToolSpec(
        name="list_data_pipelines",
        schema=pipeline.LIST_DATA_PIPELINES_SCHEMA,
        handler=pipeline.handle_list_data_pipelines,
        description="List configured data pipelines for the active farm.",
        tags=("pipeline", "ingestion"),
        emoji="🗂️",
        related_skills=("data-pipeline-setup",),
    ),
    ToolSpec(
        name="setup_initial_farm",
        schema=onboarding.SETUP_INITIAL_FARM_SCHEMA,
        handler=onboarding.handle_setup_initial_farm,
        description=(
            "Preferred first-run onboarding tool. Pass name, timezone, herd details, "
            "paddocks, and current paddock; do not call with empty args."
        ),
        tags=("farm", "onboarding"),
        emoji="🚜",
        related_skills=("farm-onboarding",),
    ),
    ToolSpec(
        name="register_farm",
        schema=farm.REGISTER_FARM_SCHEMA,
        handler=farm.handle_register_farm,
        description="Register a farm during setup or rare admin edits.",
        tags=("farm", "setup"),
        emoji="🌾",
        related_skills=("farm-onboarding",),
    ),
    ToolSpec(
        name="add_paddock",
        schema=farm.ADD_PADDOCK_SCHEMA,
        handler=farm.handle_add_paddock,
        description="Add a paddock during onboarding or maintenance.",
        tags=("farm", "paddock", "setup"),
        emoji="🗺️",
        related_skills=("farm-onboarding",),
    ),
    ToolSpec(
        name="get_farm_state",
        schema=farm.GET_FARM_STATE_SCHEMA,
        handler=farm.handle_get_farm_state,
        description=(
            "Get the current farm snapshot with herds, paddocks, recent observations, "
            "and latest plan. farm_id is optional when one farm is active."
        ),
        tags=("farm", "context"),
        emoji="📋",
        related_skills=("morning-brief", "rotation-planning"),
    ),
    ToolSpec(
        name="set_herd_position",
        schema=farm.SET_HERD_POSITION_SCHEMA,
        handler=farm.handle_set_herd_position,
        description="Set which paddock a herd is currently in.",
        tags=("herd", "paddock"),
        emoji="📍",
        related_skills=("farm-onboarding", "rotation-planning"),
    ),
    ToolSpec(
        name="record_observation",
        schema=observe.RECORD_OBSERVATION_SCHEMA,
        handler=observe.handle_record_observation,
        description=(
            "Record a farm observation or field note. Accepts source/content or the "
            "aliases type/text, and farm_id is optional when one farm is active."
        ),
        tags=("observation", "farm"),
        emoji="👀",
        related_skills=("morning-brief", "rotation-planning"),
    ),
    ToolSpec(
        name="get_paddock_state",
        schema=observe.GET_PADDOCK_STATE_SCHEMA,
        handler=observe.handle_get_paddock_state,
        description="Inspect one paddock and its recent observations.",
        tags=("paddock", "context"),
        emoji="🌱",
        related_skills=("rotation-planning",),
    ),
    ToolSpec(
        name="movement_decision",
        schema=plan.MOVEMENT_DECISION_SCHEMA,
        handler=plan.handle_movement_decision,
        description="Create a movement recommendation for a herd.",
        tags=("planning", "grazing"),
        emoji="🐄",
        related_skills=("rotation-planning",),
    ),
    ToolSpec(
        name="approve_plan",
        schema=plan.APPROVE_PLAN_SCHEMA,
        handler=plan.handle_approve_plan,
        description="Approve or reject a grazing plan.",
        tags=("planning", "approval"),
        emoji="✅",
        related_skills=("rotation-planning",),
    ),
    ToolSpec(
        name="store_lesson",
        schema=knowledge.STORE_LESSON_SCHEMA,
        handler=knowledge.handle_store_lesson,
        description="Store one ancestral knowledge lesson.",
        tags=("knowledge",),
        emoji="📚",
        related_skills=("knowledge-ingestion",),
    ),
    ToolSpec(
        name="update_lesson",
        schema=knowledge.UPDATE_LESSON_SCHEMA,
        handler=knowledge.handle_update_lesson,
        description="Update a stored knowledge lesson.",
        tags=("knowledge",),
        emoji="📝",
        related_skills=("knowledge-ingestion",),
    ),
    ToolSpec(
        name="find_similar_lessons",
        schema=knowledge.FIND_SIMILAR_LESSONS_SCHEMA,
        handler=knowledge.handle_find_similar_lessons,
        description="Find similar lessons for one author.",
        tags=("knowledge", "dedupe"),
        emoji="🔎",
        related_skills=("knowledge-ingestion",),
    ),
    ToolSpec(
        name="queue_source",
        schema=knowledge.QUEUE_SOURCE_SCHEMA,
        handler=knowledge.handle_queue_source,
        description="Queue a source for later ingestion.",
        tags=("knowledge", "queue"),
        emoji="📥",
        related_skills=("knowledge-ingestion",),
    ),
    ToolSpec(
        name="process_queue",
        schema=knowledge.PROCESS_QUEUE_SCHEMA,
        handler=knowledge.handle_process_queue,
        description="Pop queued sources for ingestion.",
        tags=("knowledge", "queue"),
        emoji="📤",
        related_skills=("knowledge-ingestion",),
    ),
    ToolSpec(
        name="search_knowledge",
        schema=knowledge.SEARCH_KNOWLEDGE_SCHEMA,
        handler=knowledge.handle_search_knowledge,
        description="Search the grazing knowledge base.",
        tags=("knowledge", "search"),
        emoji="📚",
        related_skills=("morning-brief", "rotation-planning", "knowledge-ingestion"),
    ),
    ToolSpec(
        name="list_knowledge_sources",
        schema=knowledge.LIST_KNOWLEDGE_SOURCES_SCHEMA,
        handler=knowledge.handle_list_knowledge_sources,
        description="List known knowledge sources.",
        tags=("knowledge", "sources"),
        emoji="🧾",
        related_skills=("knowledge-ingestion",),
    ),
    ToolSpec(
        name="create_ingestion_batch",
        schema=knowledge.CREATE_INGESTION_BATCH_SCHEMA,
        handler=knowledge.handle_create_ingestion_batch,
        description="Create and queue a knowledge ingestion batch.",
        tags=("knowledge", "batch"),
        emoji="🗂️",
        related_skills=("knowledge-ingestion",),
    ),
    ToolSpec(
        name="get_ingestion_batch_status",
        schema=knowledge.GET_INGESTION_BATCH_STATUS_SCHEMA,
        handler=knowledge.handle_get_ingestion_batch_status,
        description="Inspect ingestion batch progress.",
        tags=("knowledge", "batch"),
        emoji="📊",
        related_skills=("knowledge-ingestion",),
    ),
    ToolSpec(
        name="claim_ingestion_batch_item",
        schema=knowledge.CLAIM_INGESTION_BATCH_ITEM_SCHEMA,
        handler=knowledge.handle_claim_ingestion_batch_item,
        description="Claim the next source in an ingestion batch.",
        tags=("knowledge", "batch"),
        emoji="🎯",
        related_skills=("knowledge-ingestion",),
    ),
    ToolSpec(
        name="record_ingestion_batch_result",
        schema=knowledge.RECORD_INGESTION_BATCH_RESULT_SCHEMA,
        handler=knowledge.handle_record_ingestion_batch_result,
        description="Record the result of a processed batch source.",
        tags=("knowledge", "batch"),
        emoji="🧮",
        related_skills=("knowledge-ingestion",),
    ),
    ToolSpec(
        name="generate_morning_brief",
        schema=brief.GENERATE_MORNING_BRIEF_SCHEMA,
        handler=brief.handle_generate_morning_brief,
        description=(
            "Generate the current morning brief and persist the recommendation plus daily brief. "
            "farm_id is optional when one farm is active."
        ),
        tags=("briefing", "planning"),
        emoji="🌅",
        related_skills=("morning-brief", "rotation-planning"),
    ),
)


def list_tool_specs() -> tuple[ToolSpec, ...]:
    return TOOL_SPECS


def get_tool_spec(name: str) -> ToolSpec:
    for spec in TOOL_SPECS:
        if spec.name == name:
            return spec
    raise KeyError(f"Unknown openPasture tool '{name}'.")


def tool_names() -> list[str]:
    return [spec.name for spec in TOOL_SPECS]


def run_tool(name: str, args: dict[str, object] | None = None) -> str:
    return get_tool_spec(name).handler(args or {})
