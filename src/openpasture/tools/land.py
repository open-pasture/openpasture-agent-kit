"""Land report tools."""

from __future__ import annotations

from openpasture.briefing.engine import DEFAULT_DECISION_SECTIONS
from openpasture.context import get_land_service, get_store, resolve_farm_id, set_active_farm_id
from openpasture.domain import LAND_REPORT_SECTIONS, LandReportRequest
from openpasture.tools._common import (
    json_response,
    optional_bool,
    optional_datetime,
    optional_float,
    optional_mapping,
    optional_str,
)

GET_LAND_REPORT_SCHEMA = {
    "type": "object",
    "description": (
        "Get what is known about a place from Alexandria: weather, imagery, climate, hazards, soil, "
        "vegetation, species, water, terrain. Pass land_unit_id or a GeoJSON Point/Polygon geometry. "
        "Only requested sections are fetched; unfilled ones come back unavailable with a reason. "
        "Recent reports are reused unless refresh is true."
    ),
    "properties": {
        "farm_id": {"type": "string", "description": "Optional when one farm is active."},
        "land_unit_id": {"type": "string", "description": "Paddock, section, or pasture to report on."},
        "geometry": {"type": "object", "description": "GeoJSON Point, Polygon, or MultiPolygon in [lon, lat]."},
        "sections": {
            "type": ["object", "array"],
            "description": (
                "Section options keyed by name, e.g. {\"weather\": {\"forecast_days\": 10}}, or a list of names. "
                f"Names: {', '.join(LAND_REPORT_SECTIONS)}. Defaults to weather, imagery, climate, and water."
            ),
        },
        "buffer_meters": {"type": "number", "description": "Area around the geometry to include."},
        "as_of": {"type": "string", "description": "ISO 8601 time the report should describe. Defaults to now."},
        "refresh": {"type": "boolean", "description": "Fetch fresh data instead of reusing a recent report."},
    },
    "additionalProperties": True,
}


def handle_get_land_report(args: dict[str, object]) -> str:
    """Fetch (or reuse) a land report and store its sections as observations."""

    store = get_store()
    land_unit_id = optional_str(args, "land_unit_id") or optional_str(args, "paddock_id")
    geometry = optional_mapping(args, "geometry")
    land_unit_ids: list[str] | None = None
    farm_id: str | None
    if land_unit_id:
        unit = store.get_land_unit(land_unit_id)
        if unit is None:
            raise ValueError(f"Land unit '{land_unit_id}' does not exist.")
        geometry = unit.geometry.geometry
        land_unit_ids = [unit.id]
        farm_id = unit.farm_id
    elif geometry is None:
        raise ValueError("Pass land_unit_id or geometry.")
    else:
        try:
            farm_id = resolve_farm_id(args)
        except ValueError:
            farm_id = None

    request = LandReportRequest(
        geometry=geometry,
        sections=args.get("sections") or DEFAULT_DECISION_SECTIONS,  # type: ignore[arg-type]
        buffer_meters=optional_float(args, "buffer_meters"),
        as_of=optional_datetime(args, "as_of"),
    )
    report, cached = get_land_service().get_report(
        request,
        farm_id=farm_id,
        land_unit_ids=land_unit_ids,
        refresh=bool(optional_bool(args, "refresh")),
    )
    if farm_id:
        set_active_farm_id(farm_id)
    return json_response(
        status="ok",
        cached=cached,
        report=report,
        unavailable_sections={
            name: section.reason for name, section in report.sections.items() if not section.ok
        },
    )
