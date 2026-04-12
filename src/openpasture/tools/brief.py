"""Morning briefing tool surface."""

from __future__ import annotations

from datetime import date

from openpasture.briefing.assembler import MorningBriefAssembler
from openpasture.runtime import get_store, set_active_farm_id
from openpasture.tools._common import json_response, parse_date_value, require_str


GENERATE_MORNING_BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
        "for_date": {"type": "string"},
    },
    "required": ["farm_id"],
    "additionalProperties": True,
}


def handle_generate_morning_brief(args: dict[str, object]) -> str:
    """Assemble and return the current morning brief."""
    store = get_store()
    farm_id = require_str(args, "farm_id")
    requested_date = parse_date_value(args.get("for_date"), default=date.today())
    brief = MorningBriefAssembler(store=store).assemble(farm_id=farm_id, for_date=requested_date)
    store.create_plan(brief.recommendation)
    store.save_daily_brief(brief)
    set_active_farm_id(farm_id)
    return json_response(status="ok", brief=brief)
