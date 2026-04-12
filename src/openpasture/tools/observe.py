"""Observation recording and retrieval tools."""

from __future__ import annotations

from datetime import datetime

from openpasture.domain import Observation, normalize_observation_source
from openpasture.runtime import get_store, resolve_farm_id, set_active_farm_id
from openpasture.tools._common import (
    apply_argument_aliases,
    json_response,
    make_id,
    optional_str,
    optional_str_list,
    parse_datetime_value,
    require_str,
)


RECORD_OBSERVATION_SCHEMA = {
    "type": "object",
    "description": "Record a field note or other farm observation. When exactly one farm is active, farm_id can be omitted. Accepts source/content or the aliases type/text.",
    "properties": {
        "farm_id": {
            "type": "string",
            "description": "Farm id. Optional when exactly one farm is active for this instance.",
        },
        "source": {
            "type": "string",
            "description": "Observation source such as field, note, photo, or weather. Alias: type.",
        },
        "type": {
            "type": "string",
            "description": "Alias for source. Useful when the model emits type instead of source.",
        },
        "content": {
            "type": "string",
            "description": "Observation text. Alias: text.",
        },
        "text": {
            "type": "string",
            "description": "Alias for content. Useful when the model emits text instead of content.",
        },
        "observed_at": {"type": "string", "description": "Optional ISO 8601 observation timestamp."},
        "paddock_id": {"type": "string", "description": "Optional paddock id tied to the observation."},
        "herd_id": {"type": "string", "description": "Optional herd id tied to the observation."},
        "metrics": {"type": "object", "description": "Optional structured metrics captured with the observation."},
        "media_url": {"type": "string", "description": "Optional photo or media URL."},
        "tags": {"type": "array", "description": "Optional list of observation tags."},
    },
    "anyOf": [
        {"required": ["source", "content"]},
        {"required": ["source", "text"]},
        {"required": ["type", "content"]},
        {"required": ["type", "text"]},
    ],
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
    args = apply_argument_aliases(args, {"source": ("type",), "content": ("text",)})
    store = get_store()
    farm_id = resolve_farm_id(args)
    source = normalize_observation_source(require_str(args, "source"))
    observation = Observation(
        id=optional_str(args, "observation_id") or make_id("observation"),
        farm_id=farm_id,
        source=source,
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
