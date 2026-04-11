"""Morning briefing tool surface."""

from __future__ import annotations

import json


def _stub(name: str, **payload: object) -> str:
    return json.dumps({"status": "stub", "tool": name, **payload})


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
    return _stub("generate_morning_brief", args=args)
