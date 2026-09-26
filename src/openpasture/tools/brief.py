"""Morning briefing tool surface."""

from __future__ import annotations

from datetime import date

from openpasture.briefing.assembler import MorningBriefAssembler
from openpasture.context import get_store, resolve_farm_id, set_active_farm_id
from openpasture.tools._common import json_response, optional_bool, optional_str, parse_date_value


GENERATE_MORNING_BRIEF_SCHEMA = {
    "type": "object",
    "description": (
        "Generate the farmer-readable morning brief for a herd. It wraps this window's grazing decision, "
        "running the fallback decision cycle when there is none yet. farm_id is optional when exactly one "
        "farm is active."
    ),
    "properties": {
        "farm_id": {
            "type": "string",
            "description": "Farm id. Optional when exactly one farm is active for this instance.",
        },
        "herd_id": {"type": "string", "description": "Herd id. Defaults to the farm's first herd."},
        "for_date": {"type": "string", "description": "Optional ISO date to evaluate. Defaults to today."},
        "refresh": {"type": "boolean", "description": "Decide again even if this window already has a decision."},
    },
    "additionalProperties": True,
}


def handle_generate_morning_brief(args: dict[str, object]) -> str:
    """Assemble, persist, and return the current morning brief."""
    store = get_store()
    farm_id = resolve_farm_id(args)
    requested_date = parse_date_value(args.get("for_date"), default=date.today())
    brief = MorningBriefAssembler(store=store).assemble(
        farm_id=farm_id,
        for_date=requested_date,
        herd_id=optional_str(args, "herd_id"),
        refresh=bool(optional_bool(args, "refresh")),
    )
    store.save_daily_brief(brief)
    set_active_farm_id(farm_id)
    return json_response(status="ok", brief=brief)
