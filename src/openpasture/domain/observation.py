"""Observation primitives for all incoming farm signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Observation sources stay open so farm-specific pipelines can introduce
# vendor names like "nofence" without changing the domain model.
ObservationSource = str

_OBSERVATION_SOURCE_ALIASES = {
    "field": "field",
    "field-note": "field",
    "field-observation": "field",
    "manual": "field",
    "farmer": "field",
    "farmer-note": "field",
    "farmer-observation": "field",
    "note": "note",
    "manual-note": "note",
    "photo": "photo",
    "image": "photo",
    "satellite": "satellite",
    "trailcam": "trailcam",
    "trail-cam": "trailcam",
    "weather": "weather",
}


def normalize_observation_source(source: str) -> str:
    """Canonicalize tool/model-provided observation source labels."""

    normalized = source.strip().lower().replace("_", "-").replace(" ", "-")
    return _OBSERVATION_SOURCE_ALIASES.get(normalized, normalized)


def is_field_observation_source(source: str) -> bool:
    """Return True when an observation represents direct field context."""

    return normalize_observation_source(source) in {"field", "note", "photo"}


@dataclass(slots=True)
class ObservationWindow:
    """A time span over which a grouped observation applies."""

    start_at: datetime
    end_at: datetime


@dataclass(slots=True)
class Observation:
    """A unified signal about current or recent farm state."""

    id: str
    farm_id: str
    source: ObservationSource
    observed_at: datetime
    content: str
    paddock_id: str | None = None
    herd_id: str | None = None
    metrics: dict[str, object] = field(default_factory=dict)
    media_url: str | None = None
    media_thumbnail_url: str | None = None
    media_metadata: dict[str, object] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
