"""Hermes connector for the openPasture agent kit."""

from __future__ import annotations

from openpasture import runtime
from openpasture.toolkit import TOOLSET, list_tool_specs
from openpasture.tools._common import hermes_tool


def register(ctx) -> None:
    """Register openPasture tools and lifecycle hooks with Hermes."""

    runtime.initialize(delivery_handler=ctx.inject_message)
    for spec in list_tool_specs():
        kwargs = {"description": spec.description}
        if spec.emoji is not None:
            kwargs["emoji"] = spec.emoji
        ctx.register_tool(
            spec.name,
            TOOLSET,
            spec.schema,
            hermes_tool(spec.handler),
            **kwargs,
        )
    ctx.register_hook("on_session_start", runtime.on_session_start)
    ctx.register_hook("pre_llm_call", runtime.pre_llm_call)
