"""Movement planning and feedback tools."""

from __future__ import annotations

import json


def _stub(name: str, **payload: object) -> str:
    return json.dumps({"status": "stub", "tool": name, **payload})


MOVEMENT_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
        "for_date": {"type": "string"},
    },
    "required": ["farm_id", "for_date"],
    "additionalProperties": True,
}

APPROVE_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "plan_id": {"type": "string"},
        "status": {"type": "string"},
        "feedback": {"type": "string"},
    },
    "required": ["plan_id", "status"],
    "additionalProperties": True,
}


def handle_movement_decision(args: dict[str, object]) -> str:
    """Create or update the current movement recommendation."""
    return _stub("movement_decision", args=args)


def handle_approve_plan(args: dict[str, object]) -> str:
    """Record farmer approval, rejection, or modification feedback."""
    return _stub("approve_plan", args=args)
