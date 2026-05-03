"""Observation recording and retrieval tools."""

from __future__ import annotations

from datetime import datetime

from openpasture.domain import Observation, normalize_observation_source
from openpasture.context import get_store, resolve_farm_id, set_active_farm_id
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
        "media_thumbnail_url": {"type": "string", "description": "Optional thumbnail URL for the attached media."},
        "media_metadata": {"type": "object", "description": "Optional metadata for the attached media."},
        "image_file": {
            "type": "object",
            "description": "Optional ChatGPT file parameter for an uploaded or selected image.",
            "properties": {
                "download_url": {"type": "string"},
                "file_id": {"type": "string"},
                "file_name": {"type": "string"},
                "mime_type": {"type": "string"},
            },
            "additionalProperties": True,
        },
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


def _uploaded_image_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    metadata: dict[str, object] = {"source": "chatgpt_file"}
    for source_key, target_key in (
        ("file_id", "chatgpt_file_id"),
        ("fileId", "chatgpt_file_id"),
        ("file_name", "file_name"),
        ("fileName", "file_name"),
        ("mime_type", "content_type"),
        ("mimeType", "content_type"),
    ):
        item = value.get(source_key)
        if isinstance(item, str) and item.strip():
            metadata[target_key] = item.strip()
    return metadata


def _uploaded_image_download_url(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("download_url", "downloadUrl"):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def _import_uploaded_image(
    store: object,
    *,
    farm_id: str,
    image_file: object,
    fallback_url: str | None,
) -> tuple[str | None, str | None, dict[str, object]]:
    metadata = _uploaded_image_metadata(image_file)
    download_url = _uploaded_image_download_url(image_file) or fallback_url
    if not download_url:
        return fallback_url, None, metadata

    import_media = getattr(store, "import_media_from_url", None)
    if not callable(import_media):
        return download_url, None, metadata

    imported = import_media(
        download_url,
        farm_id=farm_id,
        file_id=metadata.get("chatgpt_file_id"),
        file_name=metadata.get("file_name"),
        content_type=metadata.get("content_type"),
    )
    if not isinstance(imported, dict):
        return download_url, None, metadata

    imported_url = imported.get("url")
    imported_thumbnail_url = imported.get("thumbnailUrl") or imported.get("thumbnail_url")
    imported_metadata = imported.get("metadata")
    if isinstance(imported_metadata, dict):
        metadata.update(imported_metadata)
    return (
        imported_url if isinstance(imported_url, str) and imported_url else download_url,
        imported_thumbnail_url if isinstance(imported_thumbnail_url, str) and imported_thumbnail_url else None,
        metadata,
    )


def handle_record_observation(args: dict[str, object]) -> str:
    """Persist a new observation."""
    args = apply_argument_aliases(args, {"source": ("type",), "content": ("text",)})
    store = get_store()
    farm_id = resolve_farm_id(args)
    source = normalize_observation_source(require_str(args, "source"))
    media_url = optional_str(args, "media_url")
    media_thumbnail_url = optional_str(args, "media_thumbnail_url")
    media_metadata = args.get("media_metadata") if isinstance(args.get("media_metadata"), dict) else {}
    image_file = args.get("image_file")
    if image_file is not None:
        media_url, imported_thumbnail_url, imported_metadata = _import_uploaded_image(
            store,
            farm_id=farm_id,
            image_file=image_file,
            fallback_url=media_url,
        )
        media_thumbnail_url = imported_thumbnail_url or media_thumbnail_url
        media_metadata = {**media_metadata, **imported_metadata}
    observation = Observation(
        id=optional_str(args, "observation_id") or make_id("observation"),
        farm_id=farm_id,
        source=source,
        observed_at=parse_datetime_value(args.get("observed_at"), default=datetime.utcnow()),
        content=require_str(args, "content"),
        paddock_id=optional_str(args, "paddock_id"),
        herd_id=optional_str(args, "herd_id"),
        metrics=args.get("metrics") if isinstance(args.get("metrics"), dict) else {},
        media_url=media_url,
        media_thumbnail_url=media_thumbnail_url,
        media_metadata=media_metadata,
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
    paddock = store.get_land_unit(paddock_id)
    if paddock is None or paddock.unit_type not in {"paddock", "section"}:
        raise ValueError(f"Paddock '{paddock_id}' does not exist.")
    observations = store.get_paddock_observations(paddock_id, days=7)
    set_active_farm_id(paddock.farm_id)
    return json_response(status="ok", paddock=paddock, observations=observations)
