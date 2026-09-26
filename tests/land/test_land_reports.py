from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from openpasture.context import get_default_context, get_land_service, get_store
from openpasture.domain import LandReportRequest
from openpasture.land import AlexandriaLandSource, FixtureLandSource, LandReportService, land_source_from_env
from openpasture.tools.land import handle_get_land_report

POINT = {"type": "Point", "coordinates": [-92.405, 38.125]}


def test_request_validates_sections_and_geometry():
    request = LandReportRequest(geometry=POINT, sections=["weather", "soil"], buffer_meters=2000)

    assert request.sections == {"weather": {}, "soil": {}}
    assert request.to_contract()["buffer_meters"] == 2000
    with pytest.raises(ValueError, match="Unknown land report section"):
        LandReportRequest(geometry=POINT, sections=["weather", "gold"])
    with pytest.raises(ValueError, match="Point, Polygon"):
        LandReportRequest(geometry={"type": "LineString", "coordinates": [[0, 0], [1, 1]]}, sections=["weather"])


def test_fixture_fills_only_requested_sections_and_marks_unavailable():
    source = FixtureLandSource()
    report = source.fetch(LandReportRequest(geometry=POINT, sections={"weather": {"forecast_days": 3}, "soil": {}}))

    assert set(report.sections) == {"weather", "soil"}
    weather = report.sections["weather"].to_contract()
    assert weather["status"] == "ok"
    assert len(weather["forecast"]) == 3
    assert weather["sources"][0]["provider"] == "openpasture-fixture"
    assert report.sections["soil"].to_contract() == {
        "status": "unavailable",
        "reason": "No survey coverage for this area in the fixture source.",
    }
    # Deterministic: same geometry, same numbers.
    first = source.fetch(LandReportRequest(geometry=POINT, sections=["imagery"]))
    second = source.fetch(LandReportRequest(geometry=POINT, sections=["imagery"]))
    assert first.sections["imagery"].data["ndvi_stats"] == second.sections["imagery"].data["ndvi_stats"]


def test_service_caches_by_geometry_sections_and_time(collared_farm):
    source = FixtureLandSource()
    service = LandReportService(get_store(), source, max_age=timedelta(hours=6))
    now = datetime.now(timezone.utc)
    request = LandReportRequest(geometry=collared_farm.home, sections=["weather", "imagery"], as_of=now)

    first, first_cached = service.get_report(request, farm_id=collared_farm.farm_id)
    second, second_cached = service.get_report(
        LandReportRequest(geometry=collared_farm.home, sections=["weather", "imagery"], as_of=now + timedelta(hours=1)),
        farm_id=collared_farm.farm_id,
    )
    assert (first_cached, second_cached) == (False, True)
    assert second.report_id == first.report_id
    assert len(source.calls) == 1

    # Different sections, a later time, or refresh all fetch again.
    service.get_report(LandReportRequest(geometry=collared_farm.home, sections=["weather"], as_of=now), farm_id=collared_farm.farm_id)
    service.get_report(
        LandReportRequest(geometry=collared_farm.home, sections=["weather", "imagery"], as_of=now + timedelta(hours=8)),
        farm_id=collared_farm.farm_id,
    )
    service.get_report(request, farm_id=collared_farm.farm_id, refresh=True)
    assert len(source.calls) == 4


def test_sections_are_stored_as_observations_with_provenance(collared_farm):
    service = LandReportService(get_store(), FixtureLandSource())
    report, _ = service.get_report(
        LandReportRequest(geometry=collared_farm.home, sections=["weather", "imagery", "soil"]),
        farm_id=collared_farm.farm_id,
    )

    # The Home geometry's bbox touches Home and (along the shared fence) North.
    assert set(report.land_unit_ids) == {"paddock_home", "paddock_north"}
    observations = [obs for obs in get_store().get_paddock_observations("paddock_home") if "land-report" in obs.tags]
    by_section = {obs.metrics["section"]: obs for obs in observations}
    assert set(by_section) == {"weather", "imagery"}  # soil was unavailable, so nothing to store
    assert by_section["weather"].source == "weather"
    assert by_section["imagery"].source == "satellite"
    assert by_section["imagery"].provenance["report_id"] == report.report_id
    assert by_section["imagery"].provenance["sources"][0]["provider"] == "openpasture-fixture"
    assert set(report.observation_ids) >= {obs.id for obs in observations}
    assert get_store().get_land_report(report.report_id).sections["soil"].status == "unavailable"


def test_get_land_report_tool_by_land_unit(collared_farm):
    result = json.loads(
        handle_get_land_report({"land_unit_id": "paddock_north", "sections": {"imagery": {}, "species": {}}})
    )

    assert result["cached"] is False
    assert result["report"]["land_unit_ids"] == ["paddock_north"]
    assert result["report"]["sections"]["imagery"]["status"] == "ok"
    assert "ndvi_stats" in result["report"]["sections"]["imagery"]
    assert result["unavailable_sections"] == {"species": "No species inventory in the fixture source."}
    again = json.loads(handle_get_land_report({"land_unit_id": "paddock_north", "sections": ["imagery", "species"]}))
    assert again["cached"] is True


def test_alexandria_maps_response_and_fetches_only_requested_sections(monkeypatch):
    monkeypatch.setenv("OPENPASTURE_ALEXANDRIA_LAND_PROVIDER", "openpasture")
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "auth": request.headers["authorization"], "body": json.loads(request.content)})
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "alexandria": {
                        "report_id": "lr_remote",
                        "sections": {
                            "weather": {
                                "status": "ok",
                                "current": {"air_temp_c": 14.2},
                                "sources": [{"provider": "noaa", "retrieved_at": "2026-09-25T05:58:12Z"}],
                            },
                            "soil": {"status": "unavailable", "reason": "No survey coverage for this area."},
                            "terrain": {"status": "ok", "elevation_m": 300},
                        },
                    }
                },
            },
        )

    source = AlexandriaLandSource("fc-test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    report = source.fetch(LandReportRequest(geometry=POINT, sections=["weather", "soil", "imagery"], buffer_meters=2000))

    body = seen[0]["body"]["alexandria"]
    assert seen[0]["url"] == "https://api.firecrawl.dev/v2/scrape"
    assert seen[0]["auth"] == "Bearer fc-test"
    assert (body["provider"], body["capability"]) == ("openpasture", "land_report")
    assert set(body["options"]["sections"]) == {"weather", "soil", "imagery"}
    assert body["options"]["geometry"] == POINT

    assert report.report_id == "lr_remote"
    assert set(report.sections) == {"weather", "soil", "imagery"}  # terrain was not requested
    assert report.sections["weather"].data["current"]["air_temp_c"] == 14.2
    assert report.sections["weather"].sources[0]["provider"] == "noaa"
    assert report.sections["soil"].reason == "No survey coverage for this area."
    assert report.sections["imagery"].status == "unavailable"


def test_alexandria_failure_returns_unavailable_sections():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "busy"})

    source = AlexandriaLandSource("fc-test", client=httpx.Client(transport=httpx.MockTransport(handler)))
    report = source.fetch(LandReportRequest(geometry=POINT, sections=["weather"]))

    assert report.sections["weather"].status == "unavailable"
    assert "Alexandria request failed" in (report.sections["weather"].reason or "")


def test_land_source_selection(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    assert land_source_from_env("auto").name == "open_data"
    assert land_source_from_env("fixture").name == "fixture"
    with pytest.raises(ValueError):
        land_source_from_env("alexandria")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    assert land_source_from_env("auto").name == "alexandria"
    assert get_default_context().get_land_source().name == "fixture"
    assert get_land_service().source.name == "fixture"


def test_open_data_fallback_reports_imagery_unavailable_without_network(monkeypatch):
    from openpasture.land import OpenDataLandSource

    def fake_weather(self, longitude, latitude, *, history_days, forecast_days):
        return {"current": {"air_temp_c": 20}, "history": [], "forecast": [], "sources": [{"provider": "open-meteo"}]}

    monkeypatch.setattr("openpasture.ingestion.weather.WeatherObservationPipeline.fetch_section", fake_weather)
    report = OpenDataLandSource().fetch(LandReportRequest(geometry=POINT, sections=["weather", "imagery", "soil"]))

    assert report.sections["weather"].status == "ok"
    assert report.sections["weather"].sources == [{"provider": "open-meteo"}]
    assert "not implemented" in (report.sections["imagery"].reason or "")
    assert "Alexandria" in (report.sections["soil"].reason or "")
