"""Shared helpers for tool handlers."""

from __future__ import annotations

import json
import re
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from functools import wraps
from typing import Callable, Mapping
from uuid import uuid4

from openpasture.domain import GeoPoint, GeoPolygon


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def require_str(args: dict[str, object], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' is required.")
    return value.strip()


def optional_str(args: dict[str, object], key: str) -> str | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"'{key}' must be a string.")
    stripped = value.strip()
    return stripped or None


def apply_argument_aliases(
    args: Mapping[str, object],
    aliases: Mapping[str, tuple[str, ...]],
) -> dict[str, object]:
    """Fill canonical keys from known aliases without overwriting explicit values."""

    payload = dict(args)
    for canonical, candidates in aliases.items():
        current = payload.get(canonical)
        if current not in (None, ""):
            continue
        for alias in candidates:
            value = payload.get(alias)
            if value not in (None, ""):
                payload[canonical] = value
                break
    return payload


def optional_float(args: dict[str, object], key: str) -> float | None:
    value = args.get(key)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"'{key}' must be numeric.")


def optional_int(args: dict[str, object], key: str) -> int | None:
    value = args.get(key)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise ValueError(f"'{key}' must be an integer.")


def parse_loose_int(value: object, *, key: str, default: int | None = None) -> int:
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"'{key}' is required.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+", value)
        if match is not None:
            return int(match.group(0))
    raise ValueError(f"'{key}' must contain an integer value.")


def optional_bool(args: dict[str, object], key: str) -> bool | None:
    value = args.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    raise ValueError(f"'{key}' must be a boolean.")


def optional_str_list(args: dict[str, object], key: str) -> list[str]:
    value = args.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"'{key}' must be a list of strings.")
    return [item.strip() for item in value if item.strip()]


def parse_date_value(value: object | None, *, default: date | None = None) -> date:
    if value is None:
        if default is not None:
            return default
        raise ValueError("Date value is required.")
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("Date must be an ISO 8601 string.")


def parse_datetime_value(value: object | None, *, default: datetime | None = None) -> datetime:
    if value is None:
        if default is not None:
            return default
        raise ValueError("Datetime value is required.")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise ValueError("Datetime must be an ISO 8601 string.")


def parse_geo_point(value: object | None) -> GeoPoint | None:
    if value is None:
        return None
    if isinstance(value, GeoPoint):
        return value
    if isinstance(value, dict):
        if value.get("type") == "Point":
            return GeoPoint.from_geojson(value)
        longitude = value.get("longitude")
        latitude = value.get("latitude")
        if isinstance(longitude, (int, float)) and isinstance(latitude, (int, float)):
            return GeoPoint(longitude=float(longitude), latitude=float(latitude))
        coordinates = value.get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) == 2:
            return GeoPoint(longitude=float(coordinates[0]), latitude=float(coordinates[1]))
    raise ValueError("Point must be GeoJSON or a {longitude, latitude} mapping.")


def parse_geo_polygon(value: object | None) -> GeoPolygon | None:
    if value is None:
        return None
    if isinstance(value, GeoPolygon):
        return value
    if isinstance(value, dict):
        if value.get("type") == "Polygon":
            return GeoPolygon.from_geojson(value)
        coordinates = value.get("coordinates")
        if isinstance(coordinates, list):
            points: list[GeoPoint] = []
            for item in coordinates:
                point = parse_geo_point(item)
                if point is not None:
                    points.append(point)
            return GeoPolygon(coordinates=points)
    if isinstance(value, list):
        points: list[GeoPoint] = []
        for item in value:
            point = parse_geo_point(item)
            if point is None:
                continue
            points.append(point)
        return GeoPolygon(coordinates=points)
    raise ValueError("Polygon must be GeoJSON or a list of point mappings.")


def serialize_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, GeoPoint):
        return value.to_geojson()
    if isinstance(value, GeoPolygon):
        return value.to_geojson()
    if is_dataclass(value):
        return {field.name: serialize_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    return value


def json_response(**payload: object) -> str:
    return json.dumps({key: serialize_value(value) for key, value in payload.items()}, indent=2, sort_keys=True)


_HERMES_INTERNAL_KEYS = {"task_id", "tool_call_id"}


def normalize_tool_args(
    args: Mapping[str, object] | None = None,
    kwargs: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Merge direct handler args with Hermes-injected kwargs.

    Hermes calls tool handlers with named arguments and may inject metadata such
    as ``task_id``. The repo's unit tests call handlers directly with a single
    payload dict, so this helper supports both entry points.
    """

    payload: dict[str, object] = {}
    if args is not None:
        payload.update(dict(args))
    if kwargs is not None:
        payload.update({key: value for key, value in kwargs.items() if key not in _HERMES_INTERNAL_KEYS})
    return payload


def hermes_tool(
    handler: Callable[[dict[str, object]], str],
) -> Callable[..., str]:
    """Adapt a plain payload handler to Hermes' callback signature."""

    @wraps(handler)
    def wrapped(*args: object, **kwargs: object) -> str:
        if len(args) > 1:
            raise TypeError(f"{handler.__name__} expected at most one positional payload argument.")
        payload_arg = args[0] if args else None
        if payload_arg is not None and not isinstance(payload_arg, Mapping):
            raise TypeError(f"{handler.__name__} expected a mapping payload, got {type(payload_arg).__name__}.")
        payload = normalize_tool_args(payload_arg, kwargs)
        return handler(payload)

    return wrapped
