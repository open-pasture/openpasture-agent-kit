"""Hermes plugin entry point for openPasture.

This module is intentionally lightweight. It registers tool schemas and hooks,
keeping the domain and storage concerns isolated in their own modules.
"""

from __future__ import annotations

from . import runtime
from .tools import brief, farm, knowledge, observe, plan

TOOLSET = "openpasture"


def register(ctx) -> None:
    """Register openPasture tools and lifecycle hooks with Hermes."""
    runtime.initialize()
    ctx.register_tool(
        "register_farm",
        TOOLSET,
        farm.REGISTER_FARM_SCHEMA,
        farm.handle_register_farm,
        description="Register a farm and initial herd state",
        emoji="🌾",
    )
    ctx.register_tool(
        "add_paddock",
        TOOLSET,
        farm.ADD_PADDOCK_SCHEMA,
        farm.handle_add_paddock,
        description="Add a paddock with geometry and status",
        emoji="🗺️",
    )
    ctx.register_tool(
        "get_farm_state",
        TOOLSET,
        farm.GET_FARM_STATE_SCHEMA,
        farm.handle_get_farm_state,
        description="Get the current farm context snapshot",
        emoji="📋",
    )
    ctx.register_tool(
        "set_herd_position",
        TOOLSET,
        farm.SET_HERD_POSITION_SCHEMA,
        farm.handle_set_herd_position,
        description="Set which paddock a herd is currently in",
        emoji="📍",
    )
    ctx.register_tool(
        "record_observation",
        TOOLSET,
        observe.RECORD_OBSERVATION_SCHEMA,
        observe.handle_record_observation,
        description="Record a farm observation or field note",
        emoji="👀",
    )
    ctx.register_tool(
        "get_paddock_state",
        TOOLSET,
        observe.GET_PADDOCK_STATE_SCHEMA,
        observe.handle_get_paddock_state,
        description="Inspect one paddock and its recent observations",
        emoji="🌱",
    )
    ctx.register_tool(
        "movement_decision",
        TOOLSET,
        plan.MOVEMENT_DECISION_SCHEMA,
        plan.handle_movement_decision,
        description="Create a movement recommendation for a herd",
        emoji="🐄",
    )
    ctx.register_tool(
        "approve_plan",
        TOOLSET,
        plan.APPROVE_PLAN_SCHEMA,
        plan.handle_approve_plan,
        description="Approve or reject a grazing plan",
        emoji="✅",
    )
    ctx.register_tool(
        "ingest_youtube",
        TOOLSET,
        knowledge.INGEST_YOUTUBE_SCHEMA,
        knowledge.handle_ingest_youtube,
        description="Ingest practitioner knowledge from YouTube",
        emoji="📺",
    )
    ctx.register_tool(
        "search_knowledge",
        TOOLSET,
        knowledge.SEARCH_KNOWLEDGE_SCHEMA,
        knowledge.handle_search_knowledge,
        description="Search the grazing knowledge base",
        emoji="📚",
    )
    ctx.register_tool(
        "generate_morning_brief",
        TOOLSET,
        brief.GENERATE_MORNING_BRIEF_SCHEMA,
        brief.handle_generate_morning_brief,
        description="Generate the current morning brief",
        emoji="🌅",
    )
    ctx.register_hook("on_session_start", runtime.on_session_start)
    ctx.register_hook("pre_llm_call", runtime.pre_llm_call)
