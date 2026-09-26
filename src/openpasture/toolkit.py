"""Framework-neutral Openpasture tool catalog."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from openpasture.tools import brief, collar, decision, farm, geo, knowledge, land, observe, onboarding, pipeline

ToolHandler = Callable[[dict[str, object]], str]


@dataclass(frozen=True)
class ToolSpec:
    """A portable executable capability exposed by Openpasture."""

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
        name="save_geo_onboarding_draft",
        schema=geo.SAVE_GEO_ONBOARDING_DRAFT_SCHEMA,
        handler=geo.handle_save_geo_onboarding_draft,
        description=(
            "Persist an agent-generated farm map draft from screenshot, survey, "
            "or map-clue interpretation."
        ),
        tags=("farm", "geo", "onboarding"),
        emoji="🗺️",
        related_skills=("geo-onboarding", "farm-onboarding"),
    ),
    ToolSpec(
        name="upsert_land_unit",
        schema=geo.UPSERT_LAND_UNIT_SCHEMA,
        handler=geo.handle_upsert_land_unit,
        description="Create or update one pasture, paddock, section, or related map unit.",
        tags=("farm", "geo", "map"),
        emoji="🧭",
        related_skills=("geo-onboarding",),
    ),
    ToolSpec(
        name="validate_land_unit_geometry",
        schema=geo.VALIDATE_LAND_UNIT_GEOMETRY_SCHEMA,
        handler=geo.handle_validate_land_unit_geometry,
        description="Normalize and validate GeoJSON geometry without persisting it.",
        tags=("farm", "geo", "validation"),
        emoji="📐",
        related_skills=("geo-onboarding",),
    ),
    ToolSpec(
        name="get_farm_geo_state",
        schema=geo.GET_FARM_GEO_STATE_SCHEMA,
        handler=geo.handle_get_farm_geo_state,
        description="Return farm boundary and nested land units for map rendering.",
        tags=("farm", "geo", "context"),
        emoji="🗺️",
        related_skills=("geo-onboarding",),
    ),
    ToolSpec(
        name="get_farm_map_link",
        schema=geo.GET_FARM_MAP_LINK_SCHEMA,
        handler=geo.handle_get_farm_map_link,
        description="Return the cloud map confirmation link for the active farm.",
        tags=("farm", "geo", "cloud"),
        emoji="🔗",
        related_skills=("geo-onboarding",),
    ),
    ToolSpec(
        name="get_farm_state",
        schema=farm.GET_FARM_STATE_SCHEMA,
        handler=farm.handle_get_farm_state,
        description=(
            "Get the current farm snapshot with herds, land units, recent observations, "
            "and the latest grazing decision. farm_id is optional when one farm is active."
        ),
        tags=("farm", "context"),
        emoji="📋",
        related_skills=("morning-brief", "rotation-planning"),
    ),
    ToolSpec(
        name="set_herd_position",
        schema=farm.SET_HERD_POSITION_SCHEMA,
        handler=farm.handle_set_herd_position,
        description=(
            "Set which paddock a herd is currently in. When the herd wears collars, collar fixes are the "
            "primary source of location."
        ),
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
        name="get_land_report",
        schema=land.GET_LAND_REPORT_SCHEMA,
        handler=land.handle_get_land_report,
        description=(
            "Get an Alexandria land report (weather, imagery, climate, hazards, soil, vegetation, species, "
            "water, terrain) for a land unit or GeoJSON geometry. Sections are stored as observations."
        ),
        tags=("land", "alexandria", "context"),
        emoji="🛰️",
        related_skills=("daily-grazing-decision", "pasture-assessment"),
    ),
    ToolSpec(
        name="record_collar_report",
        schema=collar.RECORD_COLLAR_REPORT_SCHEMA,
        handler=collar.handle_record_collar_report,
        description="Ingest a collar position report (fixes, cues, battery) and any boundary acknowledgements.",
        tags=("collar", "herd", "ingestion"),
        emoji="📡",
        related_skills=("daily-grazing-decision",),
    ),
    ToolSpec(
        name="get_herd_positions",
        schema=collar.GET_HERD_POSITIONS_SCHEMA,
        handler=collar.handle_get_herd_positions,
        description="Latest collar fixes and the current collar summary for a herd.",
        tags=("collar", "herd", "context"),
        emoji="📍",
        related_skills=("daily-grazing-decision",),
    ),
    ToolSpec(
        name="compute_grazing_signals",
        schema=decision.COMPUTE_GRAZING_SIGNALS_SCHEMA,
        handler=decision.handle_compute_grazing_signals,
        description=(
            "Compute grazing signals: pressure, rest days, forage, recovery, feed budget, risk flags, "
            "and herd behavior."
        ),
        tags=("calculations", "grazing", "context"),
        emoji="🧮",
        related_skills=("daily-grazing-decision", "rotation-planning"),
    ),
    ToolSpec(
        name="assemble_decision_context",
        schema=decision.ASSEMBLE_DECISION_CONTEXT_SCHEMA,
        handler=decision.handle_assemble_decision_context,
        description="Assemble everything the engine sees before today's grazing decision for a herd.",
        tags=("decision", "grazing", "context"),
        emoji="🧭",
        related_skills=("daily-grazing-decision",),
    ),
    ToolSpec(
        name="submit_grazing_decision",
        schema=decision.SUBMIT_GRAZING_DECISION_SCHEMA,
        handler=decision.handle_submit_grazing_decision,
        description=(
            "Submit STAY, MOVE, or NEEDS_INFO for a herd's window. The engine applies the farmer's autonomy "
            "setting and sends the boundary only when allowed."
        ),
        tags=("decision", "grazing", "collar"),
        emoji="🐄",
        related_skills=("daily-grazing-decision", "rotation-planning"),
    ),
    ToolSpec(
        name="respond_to_decision",
        schema=decision.RESPOND_TO_DECISION_SCHEMA,
        handler=decision.handle_respond_to_decision,
        description="Record the farmer's approve, modify (with boundary), or reject on a decision.",
        tags=("decision", "approval"),
        emoji="✅",
        related_skills=("daily-grazing-decision", "morning-brief"),
    ),
    ToolSpec(
        name="get_decision",
        schema=decision.GET_DECISION_SCHEMA,
        handler=decision.handle_get_decision,
        description="Get one grazing decision with its boundary command and acknowledgements.",
        tags=("decision", "record"),
        emoji="🗒️",
        related_skills=("daily-grazing-decision",),
    ),
    ToolSpec(
        name="list_decisions",
        schema=decision.LIST_DECISIONS_SCHEMA,
        handler=decision.handle_list_decisions,
        description="List grazing decisions, filtered by herd, status, or date range.",
        tags=("decision", "record"),
        emoji="🗂️",
        related_skills=("daily-grazing-decision", "rotation-planning"),
    ),
    ToolSpec(
        name="get_boundary_status",
        schema=collar.GET_BOUNDARY_STATUS_SCHEMA,
        handler=collar.handle_get_boundary_status,
        description="Get a boundary command, its collar acknowledgements, and which collars have not confirmed.",
        tags=("collar", "boundary"),
        emoji="🚧",
        related_skills=("daily-grazing-decision",),
    ),
    ToolSpec(
        name="set_autonomy",
        schema=decision.SET_AUTONOMY_SCHEMA,
        handler=decision.handle_set_autonomy,
        description=(
            "Set autonomy for the farm or a herd: propose (default), apply_unless_stopped, or apply. "
            "Also sets the decision window."
        ),
        tags=("decision", "settings"),
        emoji="🎚️",
        related_skills=("daily-grazing-decision", "farm-onboarding"),
    ),
    ToolSpec(
        name="evaluate_decision_outcome",
        schema=decision.EVALUATE_DECISION_OUTCOME_SCHEMA,
        handler=decision.handle_evaluate_decision_outcome,
        description="Evaluate what happened after a decision and write the outcome to the record.",
        tags=("decision", "learning"),
        emoji="🔁",
        related_skills=("daily-grazing-decision",),
    ),
    ToolSpec(
        name="run_decision_cycle",
        schema=decision.RUN_DECISION_CYCLE_SCHEMA,
        handler=decision.handle_run_decision_cycle,
        description=(
            "Run the fallback heuristic decision cycle for one herd or all herds. This is what the scheduler "
            "runs each window."
        ),
        tags=("decision", "automation"),
        emoji="⏱️",
        related_skills=("daily-grazing-decision", "morning-brief"),
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
            "Generate the farmer-readable morning brief wrapping this window's grazing decision. "
            "farm_id is optional when one farm is active."
        ),
        tags=("briefing", "decision"),
        emoji="🌅",
        related_skills=("morning-brief", "daily-grazing-decision"),
    ),
)


def list_tool_specs() -> tuple[ToolSpec, ...]:
    return TOOL_SPECS


def get_tool_spec(name: str) -> ToolSpec:
    for spec in TOOL_SPECS:
        if spec.name == name:
            return spec
    raise KeyError(f"Unknown Openpasture tool '{name}'.")


def tool_names() -> list[str]:
    return [spec.name for spec in TOOL_SPECS]


def run_tool(name: str, args: dict[str, object] | None = None) -> str:
    return get_tool_spec(name).handler(args or {})
