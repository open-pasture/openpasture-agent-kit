"""Farm setup and context retrieval tools."""

from __future__ import annotations

from datetime import datetime

from openpasture.domain import Farm, GeoPolygon, Herd, Paddock, WaterSource
from openpasture.runtime import get_store, resolve_farm_id, schedule_farm_brief, set_active_farm_id
from openpasture.tools._common import (
    json_response,
    make_id,
    optional_bool,
    optional_float,
    optional_str,
    parse_loose_int,
    parse_geo_point,
    parse_geo_polygon,
    require_str,
)


REGISTER_FARM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "timezone": {"type": "string"},
        "location": {"type": "object"},
        "boundary": {"type": "object"},
        "location_hint": {"type": "string"},
        "boundary_hint": {"type": "string"},
        "notes": {"type": "string"},
        "herd": {"type": "object"},
        "herds": {"type": "array"},
        "allow_additional_farm": {"type": "boolean"},
    },
    "required": ["name", "timezone"],
    "additionalProperties": True,
}

ADD_PADDOCK_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
        "name": {"type": "string"},
        "geometry": {"type": ["object", "array"]},
        "boundary": {"type": ["object", "array"]},
        "area_hectares": {"type": "number"},
        "status": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["farm_id", "name"],
    "additionalProperties": True,
}

SET_HERD_POSITION_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
        "herd_id": {"type": "string"},
        "paddock_id": {"type": "string"},
    },
    "required": ["herd_id", "paddock_id"],
    "additionalProperties": True,
}

GET_FARM_STATE_SCHEMA = {
    "type": "object",
    "description": "Return the current farm snapshot including herds, paddocks, recent observations, and latest plan. farm_id is optional when exactly one farm is active.",
    "properties": {
        "farm_id": {
            "type": "string",
            "description": "Farm id. Optional when exactly one farm is active for this instance.",
        },
    },
    "additionalProperties": True,
}


def _list_existing_farms(store) -> list[Farm]:
    try:
        return list(store.list_farms())
    except (AttributeError, NotImplementedError):
        return []


def _enforce_single_farm_guardrail(args: dict[str, object], store) -> None:
    if optional_bool(args, "allow_additional_farm"):
        return
    existing_farms = _list_existing_farms(store)
    if existing_farms:
        existing_names = ", ".join(farm.name for farm in existing_farms[:3])
        raise ValueError(
            "A farm is already registered for this instance. Refine the existing farm or pass "
            f"'allow_additional_farm'=true for a rare admin/setup override. Existing farm(s): {existing_names}."
        )


def _build_farm_notes(args: dict[str, object]) -> str:
    notes: list[str] = []
    if base_notes := optional_str(args, "notes"):
        notes.append(base_notes)
    if location_hint := optional_str(args, "location_hint"):
        notes.append(f"Onboarding location context: {location_hint}")
    if boundary_hint := optional_str(args, "boundary_hint"):
        notes.append(f"Onboarding boundary context: {boundary_hint}")
    return "\n\n".join(notes)


def _build_herd_payloads(args: dict[str, object]) -> list[dict[str, object]]:
    herds_payload: list[dict[str, object]] = []
    herd = args.get("herd")
    if isinstance(herd, dict):
        herds_payload.append(herd)
    herds = args.get("herds")
    if isinstance(herds, list):
        herds_payload.extend(item for item in herds if isinstance(item, dict))
    return herds_payload


def _create_herds(store, farm: Farm, args: dict[str, object]) -> list[Herd]:
    created_herds: list[Herd] = []
    for herd_payload in _build_herd_payloads(args):
        herd_model = Herd(
            id=str(herd_payload.get("id") or make_id("herd")),
            farm_id=farm.id,
            species=str(herd_payload.get("species") or "livestock"),
            count=parse_loose_int(herd_payload.get("count"), key="herd.count", default=0),
            current_paddock_id=(
                str(herd_payload["current_paddock_id"]) if herd_payload.get("current_paddock_id") else None
            ),
            animal_units=(
                float(herd_payload["animal_units"]) if herd_payload.get("animal_units") is not None else None
            ),
            notes=str(herd_payload.get("notes") or ""),
        )
        store.create_herd(herd_model)
        created_herds.append(herd_model)
    return created_herds


def _build_water_sources(args: dict[str, object]) -> list[WaterSource]:
    water_sources_payload = args.get("water_sources")
    water_sources: list[WaterSource] = []
    if isinstance(water_sources_payload, list):
        for item in water_sources_payload:
            if not isinstance(item, dict):
                continue
            water_sources.append(
                WaterSource(
                    id=str(item.get("id") or make_id("water")),
                    name=str(item.get("name") or "Water source"),
                    location=parse_geo_point(item.get("location")),
                    notes=str(item.get("notes") or ""),
                )
            )
    return water_sources


def handle_register_farm(args: dict[str, object]) -> str:
    """Create a farm record and return its identifier."""
    store = get_store()
    _enforce_single_farm_guardrail(args, store)
    farm = Farm(
        id=optional_str(args, "farm_id") or make_id("farm"),
        name=require_str(args, "name"),
        timezone=require_str(args, "timezone"),
        boundary=parse_geo_polygon(args.get("boundary")),
        location=parse_geo_point(args.get("location")),
        notes=_build_farm_notes(args),
        created_at=datetime.utcnow(),
    )
    store.create_farm(farm)
    created_herds = _create_herds(store, farm, args)

    water_sources = _build_water_sources(args)
    if water_sources:
        store.update_farm(farm.id, water_sources=water_sources)
        farm.water_sources = water_sources

    set_active_farm_id(farm.id)
    schedule_farm_brief(farm.id)
    return json_response(status="ok", farm=farm, herds=created_herds)


def handle_add_paddock(args: dict[str, object]) -> str:
    """Add a paddock to an existing farm."""
    store = get_store()
    farm_id = require_str(args, "farm_id")
    paddock = Paddock(
        id=optional_str(args, "paddock_id") or make_id("paddock"),
        farm_id=farm_id,
        name=require_str(args, "name"),
        geometry=parse_geo_polygon(args.get("geometry")) or parse_geo_polygon(args.get("boundary")) or GeoPolygon(),
        area_hectares=optional_float(args, "area_hectares"),
        notes=optional_str(args, "notes") or "",
        status=optional_str(args, "status") or "resting",
    )
    store.create_paddock(paddock)
    set_active_farm_id(farm_id)
    return json_response(status="ok", paddock=paddock)


def handle_get_farm_state(args: dict[str, object]) -> str:
    """Return an aggregated snapshot of current farm context."""
    store = get_store()
    farm_id = resolve_farm_id(args)
    farm = store.get_farm(farm_id)
    if farm is None:
        raise ValueError(f"Farm '{farm_id}' does not exist.")
    paddocks = store.list_paddocks(farm_id)
    herds = store.get_herds(farm_id)
    recent_observations = store.get_recent_observations(farm_id, days=7)
    latest_plan = store.get_latest_plan(farm_id)
    set_active_farm_id(farm_id)
    return json_response(
        status="ok",
        farm=farm,
        paddocks=paddocks,
        herds=herds,
        recent_observations=recent_observations,
        latest_plan=latest_plan,
    )


def handle_set_herd_position(args: dict[str, object]) -> str:
    """Record which paddock a herd is currently occupying."""
    store = get_store()
    herd_id = require_str(args, "herd_id")
    paddock_id = require_str(args, "paddock_id")
    paddock = store.get_paddock(paddock_id)
    if paddock is None:
        raise ValueError(f"Paddock '{paddock_id}' does not exist.")

    herds = store.get_herds(paddock.farm_id)
    herd = next((item for item in herds if item.id == herd_id), None)
    if herd is None:
        raise ValueError(f"Herd '{herd_id}' does not exist on farm '{paddock.farm_id}'.")

    store.update_herd_position(herd_id=herd_id, paddock_id=paddock_id)
    herd.current_paddock_id = paddock_id
    set_active_farm_id(paddock.farm_id)
    return json_response(status="ok", herd=herd, paddock=paddock)
