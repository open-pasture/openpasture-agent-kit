"""Hermes plugin entry point for openPasture.

This module is intentionally lightweight. It registers tool schemas and hooks,
keeping the domain and storage concerns isolated in their own modules.
"""

from __future__ import annotations

from . import runtime
from .tools._common import hermes_tool
from .tools import brief, farm, knowledge, observe, onboarding, pipeline, plan

TOOLSET = "openpasture"


def register(ctx) -> None:
    """Register openPasture tools and lifecycle hooks with Hermes."""
    runtime.initialize(delivery_handler=ctx.inject_message)
    ctx.register_tool(
        "save_data_pipeline",
        TOOLSET,
        pipeline.SAVE_DATA_PIPELINE_SCHEMA,
        hermes_tool(pipeline.handle_save_data_pipeline),
        description="Persist a learned data pipeline and write the reusable vendor skill after a Firecrawl-guided setup conversation.",
        emoji="🔌",
    )
    ctx.register_tool(
        "run_data_pipeline",
        TOOLSET,
        pipeline.RUN_DATA_PIPELINE_SCHEMA,
        hermes_tool(pipeline.handle_run_data_pipeline),
        description="Run one configured data pipeline immediately and return the collected observations.",
        emoji="📡",
    )
    ctx.register_tool(
        "list_data_pipelines",
        TOOLSET,
        pipeline.LIST_DATA_PIPELINES_SCHEMA,
        hermes_tool(pipeline.handle_list_data_pipelines),
        description="List configured data pipelines for the active farm.",
        emoji="🗂️",
    )
    ctx.register_tool(
        "setup_initial_farm",
        TOOLSET,
        onboarding.SETUP_INITIAL_FARM_SCHEMA,
        hermes_tool(onboarding.handle_setup_initial_farm),
        description="Preferred first-run onboarding tool. Pass name, timezone, herd details, paddocks, and current paddock; do not call with empty args.",
        emoji="🚜",
    )
    ctx.register_tool(
        "register_farm",
        TOOLSET,
        farm.REGISTER_FARM_SCHEMA,
        hermes_tool(farm.handle_register_farm),
        description="Register a farm during setup or rare admin edits",
        emoji="🌾",
    )
    ctx.register_tool(
        "add_paddock",
        TOOLSET,
        farm.ADD_PADDOCK_SCHEMA,
        hermes_tool(farm.handle_add_paddock),
        description="Add a paddock during onboarding or maintenance",
        emoji="🗺️",
    )
    ctx.register_tool(
        "get_farm_state",
        TOOLSET,
        farm.GET_FARM_STATE_SCHEMA,
        hermes_tool(farm.handle_get_farm_state),
        description="Get the current farm snapshot with herds, paddocks, recent observations, and latest plan. farm_id is optional when one farm is active.",
        emoji="📋",
    )
    ctx.register_tool(
        "set_herd_position",
        TOOLSET,
        farm.SET_HERD_POSITION_SCHEMA,
        hermes_tool(farm.handle_set_herd_position),
        description="Set which paddock a herd is currently in",
        emoji="📍",
    )
    ctx.register_tool(
        "record_observation",
        TOOLSET,
        observe.RECORD_OBSERVATION_SCHEMA,
        hermes_tool(observe.handle_record_observation),
        description="Record a farm observation or field note. Accepts source/content or the aliases type/text, and farm_id is optional when one farm is active.",
        emoji="👀",
    )
    ctx.register_tool(
        "get_paddock_state",
        TOOLSET,
        observe.GET_PADDOCK_STATE_SCHEMA,
        hermes_tool(observe.handle_get_paddock_state),
        description="Inspect one paddock and its recent observations",
        emoji="🌱",
    )
    ctx.register_tool(
        "movement_decision",
        TOOLSET,
        plan.MOVEMENT_DECISION_SCHEMA,
        hermes_tool(plan.handle_movement_decision),
        description="Create a movement recommendation for a herd",
        emoji="🐄",
    )
    ctx.register_tool(
        "approve_plan",
        TOOLSET,
        plan.APPROVE_PLAN_SCHEMA,
        hermes_tool(plan.handle_approve_plan),
        description="Approve or reject a grazing plan",
        emoji="✅",
    )
    ctx.register_tool(
        "store_lesson",
        TOOLSET,
        knowledge.STORE_LESSON_SCHEMA,
        hermes_tool(knowledge.handle_store_lesson),
        description="Store one ancestral knowledge lesson",
        emoji="📚",
    )
    ctx.register_tool(
        "update_lesson",
        TOOLSET,
        knowledge.UPDATE_LESSON_SCHEMA,
        hermes_tool(knowledge.handle_update_lesson),
        description="Update a stored knowledge lesson",
        emoji="📝",
    )
    ctx.register_tool(
        "find_similar_lessons",
        TOOLSET,
        knowledge.FIND_SIMILAR_LESSONS_SCHEMA,
        hermes_tool(knowledge.handle_find_similar_lessons),
        description="Find similar lessons for one author",
        emoji="🔎",
    )
    ctx.register_tool(
        "queue_source",
        TOOLSET,
        knowledge.QUEUE_SOURCE_SCHEMA,
        hermes_tool(knowledge.handle_queue_source),
        description="Queue a source for later ingestion",
        emoji="📥",
    )
    ctx.register_tool(
        "process_queue",
        TOOLSET,
        knowledge.PROCESS_QUEUE_SCHEMA,
        hermes_tool(knowledge.handle_process_queue),
        description="Pop queued sources for ingestion",
        emoji="📤",
    )
    ctx.register_tool(
        "search_knowledge",
        TOOLSET,
        knowledge.SEARCH_KNOWLEDGE_SCHEMA,
        hermes_tool(knowledge.handle_search_knowledge),
        description="Search the grazing knowledge base",
        emoji="📚",
    )
    ctx.register_tool(
        "list_knowledge_sources",
        TOOLSET,
        knowledge.LIST_KNOWLEDGE_SOURCES_SCHEMA,
        hermes_tool(knowledge.handle_list_knowledge_sources),
        description="List known knowledge sources",
        emoji="🧾",
    )
    ctx.register_tool(
        "create_ingestion_batch",
        TOOLSET,
        knowledge.CREATE_INGESTION_BATCH_SCHEMA,
        hermes_tool(knowledge.handle_create_ingestion_batch),
        description="Create and queue a knowledge ingestion batch",
        emoji="🗂️",
    )
    ctx.register_tool(
        "get_ingestion_batch_status",
        TOOLSET,
        knowledge.GET_INGESTION_BATCH_STATUS_SCHEMA,
        hermes_tool(knowledge.handle_get_ingestion_batch_status),
        description="Inspect ingestion batch progress",
        emoji="📊",
    )
    ctx.register_tool(
        "claim_ingestion_batch_item",
        TOOLSET,
        knowledge.CLAIM_INGESTION_BATCH_ITEM_SCHEMA,
        hermes_tool(knowledge.handle_claim_ingestion_batch_item),
        description="Claim the next source in an ingestion batch",
        emoji="🎯",
    )
    ctx.register_tool(
        "record_ingestion_batch_result",
        TOOLSET,
        knowledge.RECORD_INGESTION_BATCH_RESULT_SCHEMA,
        hermes_tool(knowledge.handle_record_ingestion_batch_result),
        description="Record the result of a processed batch source",
        emoji="🧮",
    )
    ctx.register_tool(
        "generate_morning_brief",
        TOOLSET,
        brief.GENERATE_MORNING_BRIEF_SCHEMA,
        hermes_tool(brief.handle_generate_morning_brief),
        description="Generate the current morning brief and persist the recommendation plus daily brief. farm_id is optional when one farm is active.",
        emoji="🌅",
    )
    ctx.register_hook("on_session_start", runtime.on_session_start)
    ctx.register_hook("pre_llm_call", runtime.pre_llm_call)
