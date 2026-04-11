"""Observation recording and retrieval tools."""

from __future__ import annotations

import json


def _stub(name: str, **payload: object) -> str:
    return json.dumps({"status": "stub", "tool": name, **payload})


RECORD_OBSERVATION_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
        "source": {"type": "string"},
        "content": {"type": "string"},
    },
    "required": ["farm_id", "source", "content"],
    "additionalProperties": True,
}

GET_PADDOCK_STATE_SCHEMA = {
    "type": "object",
    "properties": {
        "paddock_id": {"type": "string"},
    },
    "required": ["paddock_id"],
    "additionalProperties": False,
}


def handle_record_observation(args: dict[str, object]) -> str:
    """Persist a new observation."""
    return _stub("record_observation", args=args)


def handle_get_paddock_state(args: dict[str, object]) -> str:
    """Return the state of a single paddock for reasoning and planning."""
    return _stub("get_paddock_state", args=args)
