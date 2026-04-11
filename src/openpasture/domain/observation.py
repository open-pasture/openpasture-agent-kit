"""Observation primitives for all incoming farm signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

ObservationSource = Literal["satellite", "photo", "note", "weather", "trailcam", "manual"]


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
    tags: list[str] = field(default_factory=list)
