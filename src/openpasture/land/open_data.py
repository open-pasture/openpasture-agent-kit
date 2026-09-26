"""Fallback land source used when Alexandria is not configured.

It fills the weather section from Open-Meteo and the imagery section from the
satellite pipeline (which reports unavailable until STAC ingestion lands).
Every other section is unavailable with a reason that points at Alexandria.
"""

from __future__ import annotations

from logging import getLogger

from openpasture.domain import LandReport, LandReportRequest, LandReportSection
from openpasture.domain.geo import geometry_centroid
from openpasture.ingestion.satellite import SatelliteObservationPipeline
from openpasture.ingestion.weather import WeatherObservationPipeline
from openpasture.land.source import build_report

logger = getLogger(__name__)

NEEDS_ALEXANDRIA = "Only available through Alexandria. Set FIRECRAWL_API_KEY to enable it."


class OpenDataLandSource:
    name = "open_data"

    def __init__(
        self,
        weather: WeatherObservationPipeline | None = None,
        satellite: SatelliteObservationPipeline | None = None,
    ) -> None:
        self.weather = weather or WeatherObservationPipeline()
        self.satellite = satellite or SatelliteObservationPipeline()

    def fetch(self, request: LandReportRequest) -> LandReport:
        sections: dict[str, LandReportSection] = {}
        for name, options in request.sections.items():
            if name == "weather":
                sections[name] = self._weather(request, options)
            elif name == "imagery":
                sections[name] = self._imagery(request, options)
            else:
                sections[name] = LandReportSection.unavailable(NEEDS_ALEXANDRIA)
        return build_report(request, sections, source=self.name)

    def _weather(self, request: LandReportRequest, options: dict[str, object]) -> LandReportSection:
        longitude, latitude = geometry_centroid(request.geometry)
        try:
            data = self.weather.fetch_section(
                longitude,
                latitude,
                history_days=int(options.get("history_days", 30) or 30),
                forecast_days=int(options.get("forecast_days", 7) or 7),
            )
        except Exception as exc:
            logger.warning("Open-Meteo weather fallback failed: %s", exc)
            return LandReportSection.unavailable(f"Weather lookup failed: {exc}")
        sources = data.pop("sources", [])
        return LandReportSection(status="ok", data=data, sources=list(sources))  # type: ignore[arg-type]

    def _imagery(self, request: LandReportRequest, options: dict[str, object]) -> LandReportSection:
        try:
            data = self.satellite.fetch_section(request.geometry, options)
        except NotImplementedError as exc:
            return LandReportSection.unavailable(str(exc))
        except Exception as exc:
            return LandReportSection.unavailable(f"Imagery lookup failed: {exc}")
        sources = data.pop("sources", [])
        return LandReportSection(status="ok", data=data, sources=list(sources))  # type: ignore[arg-type]
