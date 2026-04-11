"""Farm and herd-oriented domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .geo import GeoPoint, GeoPolygon


@dataclass(slots=True)
class WaterSource:
    """A water source or watering area relevant to movement decisions."""

    id: str
    name: str
    location: GeoPoint | None = None
    notes: str = ""


@dataclass(slots=True)
class Paddock:
    """A bounded grazing unit within a farm."""

    id: str
    farm_id: str
    name: str
    geometry: GeoPolygon
    area_hectares: float | None = None
    notes: str = ""
    status: str = "resting"


@dataclass(slots=True)
class Herd:
    """A livestock group managed as one decision unit."""

    id: str
    farm_id: str
    species: str
    count: int
    current_paddock_id: str | None = None
    animal_units: float | None = None
    notes: str = ""


@dataclass(slots=True)
class Farm:
    """The top-level operational unit for the agent."""

    id: str
    name: str
    timezone: str
    boundary: GeoPolygon | None = None
    location: GeoPoint | None = None
    paddock_ids: list[str] = field(default_factory=list)
    herd_ids: list[str] = field(default_factory=list)
    water_sources: list[WaterSource] = field(default_factory=list)
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
