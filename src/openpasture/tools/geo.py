"""Geospatial onboarding tools for farm map setup."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable

from openpasture.context import get_store, resolve_farm_id, set_active_farm_id
from openpasture.domain import Farm, GeoFeature, LandUnit
from openpasture.tools._common import (
    json_response,
    make_id,
    optional_float,
    optional_str,
    parse_geo_feature,
    parse_geo_point,
    require_str,
)

LAND_UNIT_TYPES = {"pasture", "paddock", "section", "no_graze_zone", "water_area"}

SAVE_GEO_ONBOARDING_DRAFT_SCHEMA = {
    "type": "object",
    "description": (
        "Persist an agent-generated geospatial onboarding draft after the agent has interpreted "
        "a map screenshot, survey, or other farmer-provided location context."
    ),
    "properties": {
        "farm_id": {"type": "string"},
        "name": {"type": "string", "description": "Farm name when creating a farm."},
        "timezone": {"type": "string", "description": "Farm timezone when creating a farm."},
        "location": {"type": "object", "description": "Farm point geometry, usually the visible dropped pin."},
        "boundary": {"type": "object", "description": "Approximate farm boundary as GeoJSON Polygon/MultiPolygon."},
        "farm_boundary": {"type": "object", "description": "Alias for boundary."},
        "location_hint": {"type": "string"},
        "boundary_hint": {"type": "string"},
        "notes": {"type": "string"},
        "source": {"type": "string", "description": "Source label such as map_screenshot."},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "pastures": {"type": "array"},
        "land_units": {"type": "array"},
        "allow_additional_farm": {"type": "boolean"},
    },
    "required": [],
    "additionalProperties": True,
}

UPSERT_LAND_UNIT_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
        "id": {"type": "string"},
        "land_unit_id": {"type": "string"},
        "parent_id": {"type": "string"},
        "unit_type": {"type": "string", "enum": sorted(LAND_UNIT_TYPES)},
        "name": {"type": "string"},
        "geometry": {"type": "object"},
        "boundary": {"type": "object"},
        "confidence": {"type": "number"},
        "provenance": {"type": "object"},
        "source": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "status": {"type": "string"},
        "notes": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["farm_id", "unit_type", "name", "geometry"],
    "additionalProperties": True,
}

VALIDATE_LAND_UNIT_GEOMETRY_SCHEMA = {
    "type": "object",
    "properties": {
        "geometry": {"type": "object"},
        "boundary": {"type": "object"},
        "parent_geometry": {"type": "object"},
        "unit_type": {"type": "string"},
    },
    "required": ["geometry"],
    "additionalProperties": True,
}

GET_FARM_GEO_STATE_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
    },
    "additionalProperties": True,
}

GET_FARM_MAP_LINK_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
    },
    "additionalProperties": True,
}


def _portal_base_url() -> str | None:
    value = (
        os.environ.get("OPENPASTURE_CLOUD_BASE_URL")
        or os.environ.get("OPENPASTURE_PORTAL_BASE_URL")
        or os.environ.get("NEXT_PUBLIC_APP_URL")
    )
    return value.rstrip("/") if value else None


def _farm_map_link(farm_id: str) -> str | None:
    base_url = _portal_base_url()
    if not base_url:
        return None
    return f"{base_url}/dashboard/farm/map?farmId={farm_id}&edit=1"


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _provenance(args: dict[str, object], item: dict[str, object] | None = None) -> dict[str, object]:
    source_item = item or {}
    raw_provenance = source_item.get("provenance")
    provenance = dict(raw_provenance) if isinstance(raw_provenance, dict) else {}
    source = source_item.get("source") or args.get("source") or provenance.get("source") or "agent_inferred"
    provenance["source"] = str(source)
    evidence = _as_str_list(source_item.get("evidence")) or _as_str_list(args.get("evidence"))
    if evidence:
        provenance["evidence"] = evidence
    provenance.setdefault("created_by", "agent")
    return provenance


def _geo_feature_from_item(item: dict[str, object]) -> GeoFeature:
    feature = parse_geo_feature(item.get("geometry")) or parse_geo_feature(item.get("boundary"))
    if feature is None:
        raise ValueError("Land-unit geometry is required.")
    return feature


def _bbox_warning(unit_type: str, feature: GeoFeature, parent_feature: GeoFeature | None) -> list[str]:
    if parent_feature is None:
        return []
    if parent_feature.contains_bbox(feature):
        return []
    return [
        (
            f"{unit_type} geometry extends outside the parent boundary by bounding-box check; "
            "keep it as a draft until the farmer confirms or edits it."
        )
    ]


def _build_notes(args: dict[str, object]) -> str:
    notes: list[str] = []
    if base_notes := optional_str(args, "notes"):
        notes.append(base_notes)
    if location_hint := optional_str(args, "location_hint"):
        notes.append(f"Geo onboarding location context: {location_hint}")
    if boundary_hint := optional_str(args, "boundary_hint"):
        notes.append(f"Geo onboarding boundary context: {boundary_hint}")
    return "\n\n".join(notes)


def _create_or_load_farm(args: dict[str, object]) -> tuple[Farm, GeoFeature | None]:
    store = get_store()
    farm_id = optional_str(args, "farm_id")
    boundary_feature = parse_geo_feature(args.get("boundary")) or parse_geo_feature(args.get("farm_boundary"))

    if farm_id:
        farm = store.get_farm(farm_id)
        if farm is None:
            raise ValueError(f"Farm '{farm_id}' does not exist.")
        if boundary_feature is not None:
            store.update_farm(farm.id, boundary=boundary_feature)
            farm.boundary = boundary_feature
        if location := parse_geo_point(args.get("location")):
            store.update_farm(farm.id, location=location)
            farm.location = location
        set_active_farm_id(farm.id)
        return farm, boundary_feature

    existing_farms = list(store.list_farms())
    if existing_farms and not bool(args.get("allow_additional_farm")):
        farm = existing_farms[0]
        if boundary_feature is not None:
            store.update_farm(farm.id, boundary=boundary_feature)
            farm.boundary = boundary_feature
        if location := parse_geo_point(args.get("location")):
            store.update_farm(farm.id, location=location)
            farm.location = location
        set_active_farm_id(farm.id)
        return farm, boundary_feature

    farm = Farm(
        id=optional_str(args, "new_farm_id") or make_id("farm"),
        name=require_str(args, "name"),
        timezone=require_str(args, "timezone"),
        location=parse_geo_point(args.get("location")),
        boundary=boundary_feature,
        notes=_build_notes(args),
        created_at=datetime.utcnow(),
    )
    store.create_farm(farm)
    set_active_farm_id(farm.id)
    return farm, boundary_feature


def _confidence(args: dict[str, object], item: dict[str, object]) -> float:
    value = item.get("confidence", args.get("confidence"))
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return 0.55 if _provenance(args, item).get("source") == "map_screenshot" else 0.75


def _land_unit_from_payload(
    args: dict[str, object],
    farm_id: str,
    item: dict[str, object],
    *,
    unit_type: str,
    parent_id: str | None,
    parent_feature: GeoFeature | None,
) -> LandUnit:
    if unit_type not in LAND_UNIT_TYPES:
        raise ValueError(f"Unsupported land unit type: {unit_type}")
    feature = _geo_feature_from_item(item)
    warnings = _as_str_list(item.get("warnings"))
    warnings.extend(_bbox_warning(unit_type, feature, parent_feature))
    return LandUnit(
        id=str(item.get("land_unit_id") or item.get("id") or make_id(unit_type)),
        farm_id=farm_id,
        parent_id=parent_id or (str(item["parent_id"]) if item.get("parent_id") else None),
        unit_type=unit_type,
        name=str(item.get("name") or unit_type.title()),
        geometry=feature,
        area_hectares=optional_float(item, "area_hectares"),
        confidence=_confidence(args, item),
        provenance=_provenance(args, item),
        geometry_version=int(item.get("geometry_version") or 1),
        status=str(item.get("status") or "draft"),
        notes=str(item.get("notes") or ""),
        warnings=warnings,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def _iter_payload_items(value: object) -> Iterable[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _persist_nested_units(args: dict[str, object], farm_id: str, boundary_feature: GeoFeature | None) -> list[LandUnit]:
    store = get_store()
    created: list[LandUnit] = []

    for item in _iter_payload_items(args.get("land_units")):
        unit_type = str(item.get("unit_type") or "pasture")
        parent_feature = None
        if parent_id := item.get("parent_id"):
            parent = store.get_land_unit(str(parent_id))
            parent_feature = parent.geometry if parent else None
        land_unit = _land_unit_from_payload(
            args,
            farm_id,
            item,
            unit_type=unit_type,
            parent_id=None,
            parent_feature=parent_feature or boundary_feature,
        )
        store.upsert_land_unit(land_unit)
        created.append(land_unit)

    for pasture_payload in _iter_payload_items(args.get("pastures")):
        pasture = _land_unit_from_payload(
            args,
            farm_id,
            pasture_payload,
            unit_type="pasture",
            parent_id=None,
            parent_feature=boundary_feature,
        )
        store.upsert_land_unit(pasture)
        created.append(pasture)
        for paddock_payload in _iter_payload_items(pasture_payload.get("paddocks")):
            paddock = _land_unit_from_payload(
                args,
                farm_id,
                paddock_payload,
                unit_type="paddock",
                parent_id=pasture.id,
                parent_feature=pasture.geometry,
            )
            store.upsert_land_unit(paddock)
            created.append(paddock)
            for section_payload in _iter_payload_items(paddock_payload.get("sections")):
                section = _land_unit_from_payload(
                    args,
                    farm_id,
                    section_payload,
                    unit_type="section",
                    parent_id=paddock.id,
                    parent_feature=paddock.geometry,
                )
                store.upsert_land_unit(section)
                created.append(section)

    return created


def handle_save_geo_onboarding_draft(args: dict[str, object]) -> str:
    """Persist a full geospatial onboarding draft and return a map link."""

    farm, boundary_feature = _create_or_load_farm(args)
    land_units = _persist_nested_units(args, farm.id, boundary_feature)
    return json_response(
        status="ok",
        workflow="geo_onboarding",
        farm=farm,
        land_units=land_units,
        map_url=_farm_map_link(farm.id),
        warnings=[warning for unit in land_units for warning in unit.warnings],
    )


def handle_upsert_land_unit(args: dict[str, object]) -> str:
    """Create or update one pasture, paddock, section, or related map unit."""

    store = get_store()
    farm_id = require_str(args, "farm_id")
    parent_feature = None
    if parent_id := optional_str(args, "parent_id"):
        parent = store.get_land_unit(parent_id)
        parent_feature = parent.geometry if parent else None
    land_unit = _land_unit_from_payload(
        args,
        farm_id,
        args,
        unit_type=require_str(args, "unit_type"),
        parent_id=parent_id,
        parent_feature=parent_feature,
    )
    existing = store.get_land_unit(land_unit.id)
    if existing is not None:
        land_unit.geometry_version = existing.geometry_version + 1
        land_unit.created_at = existing.created_at
    store.upsert_land_unit(land_unit)
    set_active_farm_id(farm_id)
    return json_response(status="ok", land_unit=land_unit, map_url=_farm_map_link(farm_id))


def handle_validate_land_unit_geometry(args: dict[str, object]) -> str:
    """Normalize and validate a land-unit geometry without persisting it."""

    feature = parse_geo_feature(args.get("geometry")) or parse_geo_feature(args.get("boundary"))
    if feature is None:
        raise ValueError("Geometry is required.")
    parent_feature = parse_geo_feature(args.get("parent_geometry"))
    unit_type = optional_str(args, "unit_type") or "land_unit"
    warnings = _bbox_warning(unit_type, feature, parent_feature)
    return json_response(
        status="ok",
        geometry=feature,
        area_hectares=feature.area_hectares(),
        centroid=feature.centroid(),
        bbox=feature.bbox().to_list(),
        warnings=warnings,
    )


def handle_get_farm_geo_state(args: dict[str, object]) -> str:
    """Return farm boundary and nested land units for map rendering."""

    store = get_store()
    farm_id = resolve_farm_id(args)
    farm = store.get_farm(farm_id)
    if farm is None:
        raise ValueError(f"Farm '{farm_id}' does not exist.")
    land_units = store.list_land_units(farm_id)
    set_active_farm_id(farm_id)
    return json_response(
        status="ok",
        farm=farm,
        land_units=land_units,
        map_url=_farm_map_link(farm_id),
    )


def handle_get_farm_map_link(args: dict[str, object]) -> str:
    """Return the hosted map confirmation link for a farm."""

    farm_id = resolve_farm_id(args)
    return json_response(status="ok", farm_id=farm_id, map_url=_farm_map_link(farm_id))
