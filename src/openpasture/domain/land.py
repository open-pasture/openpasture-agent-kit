"""Land report primitives: what is known about a place.

A caller asks for a geometry and the sections it needs. Only requested
sections are fetched. Every requested section comes back either ``ok`` with its
data and sources, or ``unavailable`` with a reason. Shapes follow
``docs/contracts.md``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping

from .clock import parse_datetime, utc_now

LAND_REPORT_SECTIONS: tuple[str, ...] = (
    "weather",
    "imagery",
    "climate",
    "hazards",
    "soil",
    "vegetation",
    "species",
    "water",
    "terrain",
)
LAND_GEOMETRY_TYPES = {"Point", "Polygon", "MultiPolygon"}

SectionStatus = Literal["ok", "unavailable"]


def normalize_sections(value: object) -> dict[str, dict[str, object]]:
    """Accept a section mapping or a list of section names."""

    if value is None:
        return {}
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        sections = {str(name): {} for name in value}
    elif isinstance(value, Mapping):
        sections = {
            str(name): dict(options) if isinstance(options, Mapping) else {}
            for name, options in value.items()
        }
    else:
        raise ValueError("'sections' must be a mapping of section options or a list of section names.")
    unknown = sorted(name for name in sections if name not in LAND_REPORT_SECTIONS)
    if unknown:
        raise ValueError(
            f"Unknown land report section(s): {', '.join(unknown)}. "
            f"Supported: {', '.join(LAND_REPORT_SECTIONS)}."
        )
    return sections


def _round_coordinates(value: object) -> object:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, list):
        return [_round_coordinates(item) for item in value]
    return value


def normalize_land_geometry(value: Mapping[str, object]) -> dict[str, object]:
    """Return a bare GeoJSON geometry (Features are unwrapped)."""

    if value.get("type") == "Feature":
        inner = value.get("geometry")
        if not isinstance(inner, Mapping):
            raise ValueError("GeoJSON Feature must include a geometry object.")
        value = inner
    geometry_type = value.get("type")
    if geometry_type not in LAND_GEOMETRY_TYPES:
        raise ValueError("Land report geometry must be a GeoJSON Point, Polygon, or MultiPolygon.")
    coordinates = value.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("Land report geometry needs coordinates.")
    return {"type": geometry_type, "coordinates": coordinates}


@dataclass(slots=True)
class LandReportRequest:
    """A request for what is known about a geometry."""

    geometry: dict[str, object]
    sections: dict[str, dict[str, object]]
    buffer_meters: float | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        self.geometry = normalize_land_geometry(self.geometry)
        self.sections = normalize_sections(self.sections)
        if not self.sections:
            raise ValueError("A land report request needs at least one section.")

    def to_contract(self) -> dict[str, object]:
        payload: dict[str, object] = {"geometry": self.geometry, "sections": self.sections}
        if self.buffer_meters is not None:
            payload["buffer_meters"] = self.buffer_meters
        if self.as_of is not None:
            payload["as_of"] = self.as_of.isoformat()
        return payload

    def cache_key(self) -> str:
        """Key over geometry, buffer, and requested sections. Time is matched separately."""

        material = json.dumps(
            {
                "geometry": _round_coordinates(self.geometry),
                "buffer_meters": self.buffer_meters,
                "sections": self.sections,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


@dataclass(slots=True)
class LandReportSection:
    """One section of a land report."""

    status: SectionStatus
    data: dict[str, object] = field(default_factory=dict)
    sources: list[object] = field(default_factory=list)
    reason: str | None = None

    @classmethod
    def unavailable(cls, reason: str) -> "LandReportSection":
        return cls(status="unavailable", reason=reason)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_contract(self) -> dict[str, object]:
        if self.status != "ok":
            return {"status": "unavailable", "reason": self.reason or "No data for this section."}
        return {"status": "ok", **self.data, "sources": list(self.sources)}

    @classmethod
    def from_contract(cls, payload: Mapping[str, object]) -> "LandReportSection":
        status = str(payload.get("status") or "ok")
        if status != "ok":
            reason = payload.get("reason")
            return cls.unavailable(str(reason) if reason else "Section was not filled.")
        sources = payload.get("sources")
        data = {key: value for key, value in payload.items() if key not in {"status", "sources", "reason"}}
        return cls(status="ok", data=data, sources=list(sources) if isinstance(sources, list) else [])


@dataclass(slots=True)
class LandReport:
    """What is known about a geometry, as of a time, with provenance."""

    report_id: str
    geometry: dict[str, object]
    as_of: datetime
    sections: dict[str, LandReportSection]
    farm_id: str | None = None
    land_unit_ids: list[str] = field(default_factory=list)
    buffer_meters: float | None = None
    requested_sections: dict[str, dict[str, object]] = field(default_factory=dict)
    cache_key: str | None = None
    source: str = ""
    observation_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    def section(self, name: str) -> LandReportSection | None:
        return self.sections.get(name)

    def ok_section(self, name: str) -> dict[str, object] | None:
        section = self.sections.get(name)
        if section is None or not section.ok:
            return None
        return section.data

    def to_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "geometry": self.geometry,
            "as_of": self.as_of.isoformat(),
            "sections": {name: section.to_contract() for name, section in self.sections.items()},
            "farm_id": self.farm_id,
            "land_unit_ids": list(self.land_unit_ids),
            "buffer_meters": self.buffer_meters,
            "requested_sections": self.requested_sections,
            "cache_key": self.cache_key,
            "source": self.source,
            "observation_ids": list(self.observation_ids),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "LandReport":
        raw_sections = data.get("sections")
        sections = {
            str(name): LandReportSection.from_contract(section)
            for name, section in (raw_sections.items() if isinstance(raw_sections, Mapping) else [])
            if isinstance(section, Mapping)
        }
        buffer_meters = data.get("buffer_meters")
        requested = data.get("requested_sections")
        return cls(
            report_id=str(data["report_id"]),
            geometry=dict(data.get("geometry") or {}),  # type: ignore[arg-type]
            as_of=parse_datetime(data.get("as_of")) or utc_now(),
            sections=sections,
            farm_id=str(data["farm_id"]) if data.get("farm_id") else None,
            land_unit_ids=[str(item) for item in data.get("land_unit_ids") or []],
            buffer_meters=float(buffer_meters) if isinstance(buffer_meters, (int, float)) else None,
            requested_sections=dict(requested) if isinstance(requested, Mapping) else {},
            cache_key=str(data["cache_key"]) if data.get("cache_key") else None,
            source=str(data.get("source") or ""),
            observation_ids=[str(item) for item in data.get("observation_ids") or []],
            created_at=parse_datetime(data.get("created_at")) or utc_now(),
        )
