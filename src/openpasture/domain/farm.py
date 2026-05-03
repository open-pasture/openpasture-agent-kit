"""Farm and herd-oriented domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .geo import GeoFeature, GeoPoint, GeoPolygon


LAND_UNIT_TYPES = {"farm", "pasture", "paddock", "section", "no_graze_zone", "water_area"}


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
class LandUnit:
    """A versioned geospatial management unit within a farm."""

    id: str
    farm_id: str
    unit_type: str
    name: str
    geometry: GeoFeature
    parent_id: str | None = None
    area_hectares: float | None = None
    confidence: float = 1.0
    provenance: dict[str, object] = field(default_factory=dict)
    geometry_version: int = 1
    status: str = "draft"
    notes: str = ""
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if self.unit_type not in LAND_UNIT_TYPES:
            raise ValueError(f"Unsupported land unit type: {self.unit_type}")
        if self.area_hectares is None:
            self.area_hectares = self.geometry.area_hectares()


@dataclass(slots=True)
class Pasture:
    """A durable field or pasture within a farm boundary."""

    land_unit: LandUnit


@dataclass(slots=True)
class Section:
    """An optional temporary grazing section within a paddock."""

    land_unit: LandUnit


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
    boundary: GeoFeature | GeoPolygon | None = None
    location: GeoPoint | None = None
    paddock_ids: list[str] = field(default_factory=list)
    herd_ids: list[str] = field(default_factory=list)
    water_sources: list[WaterSource] = field(default_factory=list)
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
