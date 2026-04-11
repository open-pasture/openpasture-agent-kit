"""Hermes plugin entry point for openPasture.

This module is intentionally lightweight. It registers tool schemas and hooks,
keeping the domain and storage concerns isolated in their own modules.
"""

from __future__ import annotations

from .tools import brief, farm, knowledge, observe, plan


def _noop(*_args, **_kwargs) -> None:
    """Default hook placeholder."""


def register(ctx) -> None:
    """Register openPasture tools and lifecycle hooks with Hermes."""
    ctx.register_tool("register_farm", farm.REGISTER_FARM_SCHEMA, farm.handle_register_farm)
    ctx.register_tool("add_paddock", farm.ADD_PADDOCK_SCHEMA, farm.handle_add_paddock)
    ctx.register_tool("get_farm_state", farm.GET_FARM_STATE_SCHEMA, farm.handle_get_farm_state)
    ctx.register_tool(
        "record_observation",
        observe.RECORD_OBSERVATION_SCHEMA,
        observe.handle_record_observation,
    )
    ctx.register_tool(
        "get_paddock_state",
        observe.GET_PADDOCK_STATE_SCHEMA,
        observe.handle_get_paddock_state,
    )
    ctx.register_tool(
        "movement_decision",
        plan.MOVEMENT_DECISION_SCHEMA,
        plan.handle_movement_decision,
    )
    ctx.register_tool("approve_plan", plan.APPROVE_PLAN_SCHEMA, plan.handle_approve_plan)
    ctx.register_tool(
        "ingest_youtube",
        knowledge.INGEST_YOUTUBE_SCHEMA,
        knowledge.handle_ingest_youtube,
    )
    ctx.register_tool(
        "search_knowledge",
        knowledge.SEARCH_KNOWLEDGE_SCHEMA,
        knowledge.handle_search_knowledge,
    )
    ctx.register_tool(
        "generate_morning_brief",
        brief.GENERATE_MORNING_BRIEF_SCHEMA,
        brief.handle_generate_morning_brief,
    )
    ctx.register_hook("on_session_start", _noop)
    ctx.register_hook("pre_llm_call", _noop)
