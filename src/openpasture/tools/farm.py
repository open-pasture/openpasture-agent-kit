"""Farm setup and context retrieval tools."""

from __future__ import annotations

import json


def _stub(name: str, **payload: object) -> str:
    return json.dumps({"status": "stub", "tool": name, **payload})


REGISTER_FARM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "timezone": {"type": "string"},
    },
    "required": ["name", "timezone"],
    "additionalProperties": True,
}

ADD_PADDOCK_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
        "name": {"type": "string"},
    },
    "required": ["farm_id", "name"],
    "additionalProperties": True,
}

GET_FARM_STATE_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
    },
    "required": ["farm_id"],
    "additionalProperties": False,
}


def handle_register_farm(args: dict[str, object]) -> str:
    """Create a farm record and return its identifier."""
    return _stub("register_farm", args=args)


def handle_add_paddock(args: dict[str, object]) -> str:
    """Add a paddock to an existing farm."""
    return _stub("add_paddock", args=args)


def handle_get_farm_state(args: dict[str, object]) -> str:
    """Return an aggregated snapshot of current farm context."""
    return _stub("get_farm_state", args=args)
