"""Observation recording and retrieval tools."""

from __future__ import annotations

from datetime import datetime

from openpasture.domain import Observation
from openpasture.runtime import get_store, set_active_farm_id
from openpasture.tools._common import (
    json_response,
    make_id,
    optional_str,
    optional_str_list,
    parse_datetime_value,
    require_str,
)


RECORD_OBSERVATION_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
        "source": {"type": "string"},
        "content": {"type": "string"},
        "observed_at": {"type": "string"},
        "paddock_id": {"type": "string"},
        "herd_id": {"type": "string"},
        "metrics": {"type": "object"},
        "media_url": {"type": "string"},
        "tags": {"type": "array"},
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
    store = get_store()
    farm_id = require_str(args, "farm_id")
    observation = Observation(
        id=optional_str(args, "observation_id") or make_id("observation"),
        farm_id=farm_id,
        source=require_str(args, "source"),
        observed_at=parse_datetime_value(args.get("observed_at"), default=datetime.utcnow()),
        content=require_str(args, "content"),
        paddock_id=optional_str(args, "paddock_id"),
        herd_id=optional_str(args, "herd_id"),
        metrics=args.get("metrics") if isinstance(args.get("metrics"), dict) else {},
        media_url=optional_str(args, "media_url"),
        tags=optional_str_list(args, "tags"),
    )
    store.record_observation(observation)
    if observation.herd_id and observation.paddock_id:
        herd_ids = {herd.id for herd in store.get_herds(farm_id)}
        if observation.herd_id in herd_ids:
            # When a field note explicitly ties a herd to a paddock, treat that
            # as the best current location signal until the farmer says otherwise.
            store.update_herd_position(observation.herd_id, observation.paddock_id)
    set_active_farm_id(farm_id)
    return json_response(status="ok", observation=observation)


def handle_get_paddock_state(args: dict[str, object]) -> str:
    """Return the state of a single paddock for reasoning and planning."""
    store = get_store()
    paddock_id = require_str(args, "paddock_id")
    paddock = store.get_paddock(paddock_id)
    if paddock is None:
        raise ValueError(f"Paddock '{paddock_id}' does not exist.")
    observations = store.get_paddock_observations(paddock_id, days=7)
    set_active_farm_id(paddock.farm_id)
    return json_response(status="ok", paddock=paddock, observations=observations)
