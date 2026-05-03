"""Composite onboarding tool for first-run farm setup."""

from __future__ import annotations

import json

from openpasture.tools import farm
from openpasture.domain import Farm
from openpasture.tools._common import json_response, optional_bool, optional_str, parse_loose_int

_SETUP_INITIAL_FARM_EXAMPLE = {
    "name": "Willow Creek",
    "timezone": "America/Chicago",
    "herd": {"id": "herd_1", "species": "cattle", "count": 28},
    "paddocks": [
        {"id": "paddock_home", "name": "Home", "status": "grazing"},
        {"id": "paddock_north", "name": "North", "status": "resting"},
    ],
    "current_paddock_id": "paddock_home",
}

SETUP_INITIAL_FARM_SCHEMA = {
    "type": "object",
    "description": "Preferred first-run onboarding tool. Infer the farm, herd, paddocks, and current paddock from the user's message and call this directly. Never call it as an empty probe.",
    "properties": {
        "name": {"type": "string", "description": "Farm name."},
        "timezone": {"type": "string", "description": "Farm timezone such as America/Chicago."},
        "location": {
            "type": "object",
            "description": (
                "Structured farm point geometry when visible coordinates are known. "
                "Use GeoJSON Point coordinates in [longitude, latitude] order or a "
                "{longitude, latitude} object."
            ),
        },
        "boundary": {"type": ["object", "array"], "description": "Structured farm boundary geometry when known."},
        "location_hint": {
            "type": "string",
            "description": "Flexible onboarding context such as landmarks, screenshots, or map clues.",
        },
        "boundary_hint": {
            "type": "string",
            "description": "Flexible boundary description such as rough polygons or named landmarks.",
        },
        "notes": {"type": "string", "description": "Additional onboarding notes to preserve."},
        "herd": {
            "type": "object",
            "description": "Preferred nested herd payload.",
            "properties": {
                "id": {"type": "string", "description": "Initial herd id."},
                "species": {"type": "string", "description": "Species such as cattle or sheep."},
                "count": {"type": ["integer", "string"], "description": "Animal count. Strings like '28 head' are accepted."},
                "current_paddock_id": {"type": "string", "description": "Optional current paddock id."},
            },
            "additionalProperties": True,
        },
        "herd_id": {"type": "string", "description": "Top-level alias for herd.id."},
        "herd_species": {"type": "string", "description": "Top-level alias for herd.species."},
        "herd_count": {
            "type": ["integer", "string"],
            "description": "Top-level alias for herd.count. Strings like '28 head' are accepted.",
        },
        "paddocks": {
            "type": "array",
            "description": "Initial paddocks to create.",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Paddock id alias."},
                    "paddock_id": {"type": "string", "description": "Paddock id."},
                    "name": {"type": "string", "description": "Paddock name."},
                    "geometry": {"type": ["object", "array"], "description": "Structured paddock geometry when known."},
                    "boundary": {"type": ["object", "array"], "description": "Boundary alias for geometry."},
                    "boundary_hint": {"type": "string", "description": "Flexible paddock boundary description."},
                    "status": {"type": "string", "description": "Use 'grazing' for the current paddock when helpful."},
                    "notes": {"type": "string", "description": "Additional paddock notes."},
                },
                "additionalProperties": True,
            },
        },
        "water_sources": {"type": "array", "description": "Optional initial farm water sources."},
        "current_paddock_id": {"type": "string", "description": "Current paddock id for the first herd."},
        "current_paddock_name": {"type": "string", "description": "Current paddock name alias when only the name is known."},
        "allow_additional_farm": {"type": "boolean", "description": "Rare admin override for adding another farm."},
    },
    "required": ["name", "timezone"],
    "anyOf": [
        {"required": ["herd"]},
        {"required": ["herd_id", "herd_species", "herd_count"]},
    ],
    "examples": [_SETUP_INITIAL_FARM_EXAMPLE],
    "additionalProperties": True,
}


def _build_paddock_notes(payload: dict[str, object]) -> str:
    notes: list[str] = []
    if base_notes := optional_str(payload, "notes"):
        notes.append(base_notes)
    if boundary_hint := optional_str(payload, "boundary_hint"):
        notes.append(f"Onboarding paddock boundary context: {boundary_hint}")
    return "\n\n".join(notes)


def _setup_example_json() -> str:
    return json.dumps(_SETUP_INITIAL_FARM_EXAMPLE, indent=2, sort_keys=True)


def _missing_onboarding_args_error(*, missing: list[str]) -> ValueError:
    joined = ", ".join(missing)
    return ValueError(
        "setup_initial_farm needs "
        f"{joined}. Do not call it with empty args. "
        "Pass either herd={id,species,count} or the top-level aliases herd_id, herd_species, and herd_count. "
        f"Example payload:\n{_setup_example_json()}"
    )


def _resolve_herd_payload(args: dict[str, object]) -> dict[str, object]:
    herd_payload = dict(args["herd"]) if isinstance(args.get("herd"), dict) else {}
    alias_candidates = {
        "id": ("herd_id",),
        "species": ("herd_species", "species"),
        "count": ("herd_count", "count"),
        "current_paddock_id": ("current_paddock_id",),
    }
    for key, aliases in alias_candidates.items():
        if herd_payload.get(key) not in (None, ""):
            continue
        for alias in aliases:
            value = args.get(alias)
            if value not in (None, ""):
                herd_payload[key] = value
                break

    if not herd_payload:
        raise _missing_onboarding_args_error(missing=["the first herd"])

    if herd_payload.get("count") is not None:
        herd_payload["count"] = parse_loose_int(herd_payload.get("count"), key="herd_count", default=0)
    return herd_payload


def _resolve_current_paddock_by_name(args: dict[str, object], paddocks: list[dict[str, object]]) -> str | None:
    current_paddock_name = optional_str(args, "current_paddock_name")
    if current_paddock_name is None:
        return None
    normalized = current_paddock_name.casefold()
    for paddock in paddocks:
        name = paddock.get("name")
        paddock_id = paddock.get("id")
        if isinstance(name, str) and isinstance(paddock_id, str) and name.casefold() == normalized:
            return paddock_id
    return None


def _infer_current_paddock_id(
    args: dict[str, object],
    herd_payload: dict[str, object],
    paddocks: list[dict[str, object]],
) -> str | None:
    if current_paddock_id := optional_str(args, "current_paddock_id"):
        return current_paddock_id
    current_from_herd = herd_payload.get("current_paddock_id")
    if isinstance(current_from_herd, str) and current_from_herd.strip():
        return current_from_herd.strip()
    if current_from_name := _resolve_current_paddock_by_name(args, paddocks):
        return current_from_name
    for paddock in paddocks:
        if paddock.get("status") == "grazing" and isinstance(paddock.get("id"), str):
            return str(paddock["id"])
    if len(paddocks) == 1 and isinstance(paddocks[0].get("id"), str):
        return str(paddocks[0]["id"])
    return None


def _merge_notes(existing_notes: str, new_notes: str) -> str:
    if not new_notes:
        return existing_notes
    if not existing_notes:
        return new_notes
    if new_notes in existing_notes:
        return existing_notes
    return f"{existing_notes}\n\n{new_notes}"


def _resolve_existing_farm_for_onboarding(args: dict[str, object], store) -> Farm | None:
    if optional_bool(args, "allow_additional_farm"):
        return None

    requested_farm_id = optional_str(args, "farm_id")
    existing_farms = farm._list_existing_farms(store)
    if requested_farm_id:
        existing_farm = store.get_farm(requested_farm_id)
        if existing_farm is not None:
            return existing_farm
        if existing_farms:
            raise ValueError(
                f"Farm '{requested_farm_id}' does not exist. Refine an existing farm or pass "
                "'allow_additional_farm'=true for a rare admin/setup override."
            )
        return None

    if not existing_farms:
        return None
    if len(existing_farms) == 1:
        return existing_farms[0]

    existing_names = ", ".join(item.name for item in existing_farms[:3])
    raise ValueError(
        "Multiple farms are already registered for this instance. Pass 'farm_id' to refine "
        f"one existing farm or 'allow_additional_farm'=true for a rare admin/setup override. "
        f"Existing farm(s): {existing_names}."
    )


def _update_existing_farm_for_onboarding(args: dict[str, object], existing_farm: Farm, store) -> Farm:
    updates: dict[str, object] = {
        "name": optional_str(args, "name"),
        "timezone": optional_str(args, "timezone"),
    }
    if "boundary" in args:
        updates["boundary"] = farm._parse_farm_boundary(args.get("boundary"))
    if "location" in args:
        updates["location"] = farm.parse_geo_point(args.get("location"))
    if new_notes := farm._build_farm_notes(args):
        updates["notes"] = _merge_notes(existing_farm.notes, new_notes)
    if "water_sources" in args:
        updates["water_sources"] = farm._build_water_sources(args)

    store.update_farm(existing_farm.id, **updates)
    farm.set_active_farm_id(existing_farm.id)
    farm.schedule_farm_brief(existing_farm.id)
    return store.get_farm(existing_farm.id) or existing_farm


def _save_farm_for_onboarding(args: dict[str, object], herd_payload: dict[str, object]) -> tuple[str, str]:
    store = farm.get_store()
    existing_farm = _resolve_existing_farm_for_onboarding(args, store)
    if existing_farm is None:
        register_result = json.loads(farm.handle_register_farm({**args, "herd": herd_payload}))
        return register_result["farm"]["id"], register_result["herds"][0]["id"]

    updated_farm = _update_existing_farm_for_onboarding(args, existing_farm, store)
    existing_herds = store.get_herds(updated_farm.id)
    if existing_herds:
        requested_herd_id = herd_payload.get("id")
        matched_herd = next(
            (item for item in existing_herds if isinstance(requested_herd_id, str) and item.id == requested_herd_id),
            existing_herds[0],
        )
        return updated_farm.id, matched_herd.id

    created_herds = farm._create_herds(store, updated_farm, {"herd": herd_payload})
    if not created_herds:
        raise ValueError("setup_initial_farm needs the first herd.")
    return updated_farm.id, created_herds[0].id


def _list_paddocks_for_inference(farm_id: str) -> list[dict[str, object]]:
    store = farm.get_store()
    return [
        {"id": item.id, "name": item.name, "status": item.status}
        for item in store.list_land_units(farm_id)
        if item.unit_type in {"paddock", "section"}
    ]


def handle_setup_initial_farm(args: dict[str, object]) -> str:
    """Create the common alpha onboarding state in one tool call."""

    missing: list[str] = []
    if not optional_str(args, "name"):
        missing.append("name")
    if not optional_str(args, "timezone"):
        missing.append("timezone")
    if missing:
        raise _missing_onboarding_args_error(missing=missing)
    herd_payload = _resolve_herd_payload(args)

    farm_payload = {
        key: args[key]
        for key in (
            "farm_id",
            "name",
            "timezone",
            "location",
            "boundary",
            "location_hint",
            "boundary_hint",
            "notes",
            "water_sources",
            "allow_additional_farm",
        )
        if key in args
    }

    farm_id, herd_id = _save_farm_for_onboarding(farm_payload, herd_payload)

    created_paddocks: list[dict[str, object]] = []
    paddocks_payload = args.get("paddocks")
    if isinstance(paddocks_payload, list):
        for item in paddocks_payload:
            if not isinstance(item, dict):
                continue
            paddock_payload = {
                "farm_id": farm_id,
                "name": item.get("name"),
                "paddock_id": item.get("paddock_id") or item.get("id"),
                "geometry": item.get("geometry"),
                "boundary": item.get("boundary"),
                "area_hectares": item.get("area_hectares"),
                "status": item.get("status"),
                "notes": _build_paddock_notes(item),
            }
            paddock_result = json.loads(farm.handle_add_paddock(paddock_payload))
            created_paddocks.append(paddock_result["paddock"])

    available_paddocks = _list_paddocks_for_inference(farm_id)
    current_paddock_id = _infer_current_paddock_id(
        args,
        herd_payload,
        created_paddocks or available_paddocks,
    )
    if current_paddock_id is not None:
        farm.handle_set_herd_position({"herd_id": herd_id, "paddock_id": current_paddock_id})

    state = json.loads(farm.handle_get_farm_state({"farm_id": farm_id}))
    return json_response(
        status="ok",
        workflow="onboarding",
        onboarding_status={
            "farm_ready": True,
            "herd_ready": bool(state["herds"]),
            "paddocks_ready": bool(state["paddocks"]),
            "herd_position_ready": all(herd["current_paddock_id"] for herd in state["herds"]),
        },
        farm=state["farm"],
        herds=state["herds"],
        land_units=state["land_units"],
        paddocks=state["paddocks"],
        latest_plan=state["latest_plan"],
        recent_observations=state["recent_observations"],
    )
