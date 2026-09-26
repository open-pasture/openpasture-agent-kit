"""Land report service: caching, coverage, and observation storage.

Every report is saved. Each ``ok`` section is also recorded as an Observation
on each land unit the geometry covers, with the report id and section sources
as provenance, so the farm's own record carries what the engine saw.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from openpasture.domain import LandReport, LandReportRequest, LandReportSection, LandUnit, Observation
from openpasture.domain.clock import as_utc, utc_now
from openpasture.domain.geo import bboxes_intersect, geometry_bbox
from openpasture.land.source import LandSource
from openpasture.store.protocol import FarmStore

DEFAULT_MAX_AGE = timedelta(hours=6)
COVERAGE_UNIT_TYPES = {"pasture", "paddock", "section"}
_SECTION_OBSERVATION_SOURCE = {"weather": "weather", "imagery": "satellite"}


class LandReportService:
    """Gets land reports through a LandSource, reusing recent ones."""

    def __init__(self, store: FarmStore, source: LandSource, *, max_age: timedelta | None = None) -> None:
        self.store = store
        self.source = source
        self.max_age = max_age or DEFAULT_MAX_AGE

    def get_report(
        self,
        request: LandReportRequest,
        *,
        farm_id: str | None = None,
        land_unit_ids: list[str] | None = None,
        refresh: bool = False,
    ) -> tuple[LandReport, bool]:
        """Return ``(report, from_cache)``.

        A cached report matches when geometry, buffer, and requested sections are
        the same and its ``as_of`` is within ``max_age`` of the requested time.
        """

        as_of = request.as_of or utc_now()
        cache_key = request.cache_key()
        if not refresh:
            cached = self.store.find_land_report(cache_key, as_of - self.max_age, as_of + self.max_age)
            if cached is not None:
                return cached, True

        report = self.source.fetch(request)
        report.cache_key = cache_key
        report.farm_id = farm_id
        if farm_id is not None:
            units = self._resolve_units(farm_id, request, land_unit_ids)
            report.land_unit_ids = [unit.id for unit in units]
            report.observation_ids = self._record_observations(report, farm_id, units)
        self.store.save_land_report(report)
        return report, False

    def report_for_land_unit(
        self,
        unit: LandUnit,
        sections: dict[str, dict[str, object]],
        *,
        buffer_meters: float | None = None,
        as_of: datetime | None = None,
        refresh: bool = False,
    ) -> tuple[LandReport, bool]:
        request = LandReportRequest(
            geometry=unit.geometry.geometry,
            sections=sections,
            buffer_meters=buffer_meters,
            as_of=as_of,
        )
        return self.get_report(request, farm_id=unit.farm_id, land_unit_ids=[unit.id], refresh=refresh)

    def covered_land_units(self, farm_id: str, geometry: dict[str, object], buffer_meters: float | None) -> list[LandUnit]:
        area = geometry_bbox(geometry, buffer_meters or 0.0)
        covered = []
        for unit in self.store.list_land_units(farm_id):
            if unit.unit_type not in COVERAGE_UNIT_TYPES:
                continue
            try:
                if bboxes_intersect(area, unit.geometry.bbox()):
                    covered.append(unit)
            except ValueError:
                continue
        return covered

    def _resolve_units(
        self, farm_id: str, request: LandReportRequest, land_unit_ids: list[str] | None
    ) -> list[LandUnit]:
        if land_unit_ids:
            units = [self.store.get_land_unit(unit_id) for unit_id in land_unit_ids]
            return [unit for unit in units if unit is not None]
        return self.covered_land_units(farm_id, request.geometry, request.buffer_meters)

    def _record_observations(self, report: LandReport, farm_id: str, units: list[LandUnit]) -> list[str]:
        observation_ids: list[str] = []
        targets: list[str | None] = [unit.id for unit in units] or [None]
        # Observations use naive UTC like the rest of the observation table.
        observed_at = as_utc(report.as_of).replace(tzinfo=None)
        for name, section in report.sections.items():
            if not section.ok:
                continue
            for unit_id in targets:
                observation = Observation(
                    id=f"obs_{report.report_id}_{name}_{unit_id or 'area'}",
                    farm_id=farm_id,
                    source=_SECTION_OBSERVATION_SOURCE.get(name, "land_report"),
                    observed_at=observed_at,
                    content=summarize_section(name, section),
                    paddock_id=unit_id,
                    metrics={"section": name, **section_metrics(name, section)},
                    tags=["land-report", name],
                    provenance={
                        "report_id": report.report_id,
                        "section": name,
                        "land_source": report.source,
                        "sources": section.sources,
                    },
                )
                self.store.record_observation(observation)
                observation_ids.append(observation.id)
        return observation_ids


def section_metrics(name: str, section: LandReportSection) -> dict[str, object]:
    """The compact part of a section worth keeping on each observation.

    The full section stays on the land report; observations keep what a farmer
    or agent would scan in a feed.
    """

    data = section.data
    if name == "weather":
        return {"current": data.get("current"), "forecast": (data.get("forecast") or [])[:3]}  # type: ignore[index]
    if name == "imagery":
        latest = data.get("latest") if isinstance(data.get("latest"), dict) else {}
        return {
            "ndvi_stats": data.get("ndvi_stats"),
            "captured_at": latest.get("captured_at"),  # type: ignore[union-attr]
            "cloud_cover": latest.get("cloud_cover"),  # type: ignore[union-attr]
        }
    return dict(data)


def summarize_section(name: str, section: LandReportSection) -> str:
    data = section.data
    if name == "weather":
        current = data.get("current") if isinstance(data.get("current"), dict) else {}
        forecast = data.get("forecast") if isinstance(data.get("forecast"), list) else []
        rain_ahead = sum(
            float(day.get("precip_mm") or 0) for day in forecast[:3] if isinstance(day, dict)  # type: ignore[union-attr]
        )
        return (
            f"Weather: {current.get('air_temp_c', 'unknown')}C now, "  # type: ignore[union-attr]
            f"{current.get('precip_mm_24h', 0)} mm in the last 24h, "  # type: ignore[union-attr]
            f"{round(rain_ahead, 1)} mm forecast over the next 3 days."
        )
    if name == "imagery":
        stats = data.get("ndvi_stats") if isinstance(data.get("ndvi_stats"), dict) else {}
        latest = data.get("latest") if isinstance(data.get("latest"), dict) else {}
        captured = str(latest.get("captured_at") or "unknown date")[:10]  # type: ignore[union-attr]
        return f"Imagery {captured}: NDVI mean {stats.get('mean', 'unknown')}."  # type: ignore[union-attr]
    return f"Land report {name} data."
