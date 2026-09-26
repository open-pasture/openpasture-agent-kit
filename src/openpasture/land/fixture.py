"""Deterministic, offline land source for tests and demos."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from openpasture.domain import LandReport, LandReportRequest, LandReportSection
from openpasture.domain.clock import utc_now
from openpasture.land.source import build_report

# Sections the fixture leaves unfilled by default, mirroring a place with no
# soil survey and no species inventory.
DEFAULT_UNAVAILABLE = {
    "soil": "No survey coverage for this area in the fixture source.",
    "species": "No species inventory in the fixture source.",
}


class FixtureLandSource:
    """Returns stable, plausible land data derived from the geometry itself.

    The same geometry always gives the same numbers, and different paddocks give
    different NDVI, so decisions over fixture data are repeatable. ``overrides``
    replaces a section's data; ``unavailable`` marks sections unfilled.
    """

    name = "fixture"

    def __init__(
        self,
        *,
        overrides: dict[str, dict[str, object]] | None = None,
        unavailable: dict[str, str] | None = None,
    ) -> None:
        self.overrides = dict(overrides or {})
        self.unavailable = dict(DEFAULT_UNAVAILABLE if unavailable is None else unavailable)
        self.calls: list[LandReportRequest] = []

    def fetch(self, request: LandReportRequest) -> LandReport:
        self.calls.append(request)
        seed = int(hashlib.sha256(json.dumps(request.geometry, sort_keys=True).encode()).hexdigest()[:8], 16)
        as_of = request.as_of or utc_now()
        sources = [{"provider": "openpasture-fixture", "retrieved_at": as_of.isoformat(), "license": "test data"}]
        sections: dict[str, LandReportSection] = {}
        for name, options in request.sections.items():
            if name in self.unavailable and name not in self.overrides:
                sections[name] = LandReportSection.unavailable(self.unavailable[name])
                continue
            data = self.overrides.get(name) or self._section(name, options, seed, as_of)
            sections[name] = LandReportSection(status="ok", data=dict(data), sources=list(sources))
        return build_report(request, sections, source=self.name)

    def _section(self, name: str, options: dict[str, object], seed: int, as_of) -> dict[str, object]:
        day = as_of.date()
        if name == "weather":
            history_days = int(options.get("history_days", 7) or 7)
            forecast_days = int(options.get("forecast_days", 5) or 5)
            return {
                "current": {"air_temp_c": 18.0, "precip_mm_24h": 0.0, "wind_kph": 9, "relative_humidity": 0.62},
                "history": [
                    {
                        "date": (day - timedelta(days=offset)).isoformat(),
                        "precip_mm": 2.0 if offset % 4 == 0 else 0.0,
                        "temp_max_c": 26.0,
                        "temp_min_c": 12.0,
                        "et0_mm": 3.5,
                    }
                    for offset in range(min(history_days, 30), 0, -1)
                ],
                "forecast": [
                    {
                        "date": (day + timedelta(days=offset)).isoformat(),
                        "precip_mm": 4.0 if offset == 2 else 0.0,
                        "precip_probability": 0.5 if offset == 2 else 0.1,
                        "temp_max_c": 25.0,
                        "temp_min_c": 11.0,
                    }
                    for offset in range(1, forecast_days + 1)
                ],
            }
        if name == "imagery":
            ndvi = round(0.45 + (seed % 30) / 100.0, 2)
            return {
                "latest": {
                    "captured_at": (as_of - timedelta(days=2)).isoformat(),
                    "cloud_cover": 0.03,
                    "resolution_meters": 3.0,
                    "assets": {"rgb": "fixture://rgb", "ndvi": "fixture://ndvi"},
                },
                "ndvi_stats": {"mean": ndvi, "p10": round(ndvi - 0.12, 2), "p90": round(ndvi + 0.1, 2)},
                "history": [
                    {"captured_at": (as_of - timedelta(days=days)).isoformat(), "ndvi_mean": round(ndvi - days / 300, 3)}
                    for days in (30, 16)
                ],
            }
        if name == "climate":
            return {"drought": {"category": "none", "index": 0.1}, "precipitation_normals": {"annual_mm": 1050}}
        if name == "hazards":
            return {"flood": {"events_30y": 1}, "fire": {"events_30y": 0}, "severe_weather": {"events_30y": 4}}
        if name == "vegetation":
            return {"native": ["big bluestem", "eastern gamagrass"], "invasive": ["sericea lespedeza"], "toxic_to_livestock": []}
        if name == "water":
            return {"surface_water": [], "wetlands": [], "floodplain": {"in_floodplain": False}}
        if name == "terrain":
            return {"elevation_m": 290 + seed % 40, "slope_percent": round(2 + (seed % 7) * 0.5, 1), "aspect": "south"}
        return {"note": f"Fixture {name} data."}
