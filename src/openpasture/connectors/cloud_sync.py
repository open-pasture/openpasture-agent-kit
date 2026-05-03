"""Best-effort sync from hosted agent-kit state into OpenPasture Cloud."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any
from urllib import request as urllib_request

from openpasture.context import get_store
from openpasture.tools._common import serialize_value

SYNC_TABLE_ORDER = ("farms", "paddocks", "landUnits", "herds", "observations")
LAND_UNIT_SYNC_TYPES = {"pasture", "paddock", "section", "no_graze_zone", "water_area"}


def _now_ms() -> int:
    return int(datetime.now(tz=UTC).timestamp() * 1000)


def _timestamp_ms(value: object, *, fallback: int) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            return int(datetime.fromisoformat(normalized).timestamp() * 1000)
        except ValueError:
            return fallback
    return fallback


def _string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _integer(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _compact(record: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in record.items() if value is not None}


def _append_land_unit_batches(
    batches: dict[str, list[dict[str, object]]],
    summary: dict[str, Any],
    *,
    agent_farm_id: str,
    timestamp: int,
) -> None:
    land_units = summary.get("land_units") if isinstance(summary.get("land_units"), list) else []
    for land_unit in land_units:
        if not isinstance(land_unit, dict):
            continue
        unit_type = _string(land_unit.get("unit_type"))
        if unit_type not in LAND_UNIT_SYNC_TYPES:
            continue
        agent_land_unit_id = _string(land_unit.get("id"))
        geometry = land_unit.get("geometry")
        if agent_land_unit_id is None or not isinstance(geometry, dict):
            continue
        confidence = _number(land_unit.get("confidence"))
        batches["landUnits"].append(
            _compact(
                {
                    "agentFarmId": _string(land_unit.get("farm_id")) or agent_farm_id,
                    "agentLandUnitId": agent_land_unit_id,
                    "parentId": _string(land_unit.get("parent_id")),
                    "unitType": unit_type,
                    "name": _string(land_unit.get("name")) or "Land unit",
                    "geometry": geometry,
                    "areaHectares": _number(land_unit.get("area_hectares")),
                    "confidence": confidence if confidence is not None else 1.0,
                    "provenance": (
                        land_unit.get("provenance")
                        if isinstance(land_unit.get("provenance"), dict)
                        else {}
                    ),
                    "geometryVersion": _integer(land_unit.get("geometry_version"), default=1),
                    "status": _string(land_unit.get("status")) or "draft",
                    "notes": _string(land_unit.get("notes")),
                    "warnings": _string_list(land_unit.get("warnings")),
                    "syncedAt": timestamp,
                }
            )
        )


def build_onboarding_sync_batches(
    summary: dict[str, Any],
    *,
    synced_at: int | None = None,
) -> list[dict[str, object]]:
    """Map an onboarding summary into Convex /sync batch payloads."""

    farm = summary.get("farm") if isinstance(summary.get("farm"), dict) else None
    if farm is None:
        return []

    agent_farm_id = _string(farm.get("id"))
    if agent_farm_id is None:
        return []

    timestamp = synced_at or _now_ms()
    batches: dict[str, list[dict[str, object]]] = {table: [] for table in SYNC_TABLE_ORDER}

    batches["farms"].append(
        _compact(
            {
                "agentFarmId": agent_farm_id,
                "name": _string(farm.get("name")) or "OpenPasture farm",
                "timezone": _string(farm.get("timezone")) or "UTC",
                "notes": _string(farm.get("notes")),
                "location": farm.get("location"),
                "boundary": farm.get("boundary"),
                "syncedAt": timestamp,
            }
        )
    )

    _append_land_unit_batches(batches, summary, agent_farm_id=agent_farm_id, timestamp=timestamp)

    paddocks = summary.get("paddocks") if isinstance(summary.get("paddocks"), list) else []
    for paddock in paddocks:
        if not isinstance(paddock, dict):
            continue
        agent_paddock_id = _string(paddock.get("id"))
        if agent_paddock_id is None:
            continue
        batches["paddocks"].append(
            _compact(
                {
                    "agentFarmId": agent_farm_id,
                    "agentPaddockId": agent_paddock_id,
                    "name": _string(paddock.get("name")) or "Paddock",
                    "geometry": paddock.get("geometry"),
                    "areaHectares": _number(paddock.get("area_hectares")),
                    "notes": _string(paddock.get("notes")),
                    "status": _string(paddock.get("status")) or "resting",
                    "syncedAt": timestamp,
                }
            )
        )

    herds = summary.get("herds") if isinstance(summary.get("herds"), list) else []
    for herd in herds:
        if not isinstance(herd, dict):
            continue
        agent_herd_id = _string(herd.get("id"))
        if agent_herd_id is None:
            continue
        count = herd.get("count")
        batches["herds"].append(
            _compact(
                {
                    "agentFarmId": agent_farm_id,
                    "agentHerdId": agent_herd_id,
                    "species": _string(herd.get("species")) or "livestock",
                    "count": int(count) if isinstance(count, (int, float)) else 0,
                    "currentPaddockId": _string(herd.get("current_paddock_id")),
                    "animalUnits": _number(herd.get("animal_units")),
                    "notes": _string(herd.get("notes")),
                    "syncedAt": timestamp,
                }
            )
        )

    observations = (
        summary.get("recent_observations")
        if isinstance(summary.get("recent_observations"), list)
        else []
    )
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        agent_observation_id = _string(observation.get("id"))
        if agent_observation_id is None:
            continue
        batches["observations"].append(
            _compact(
                {
                    "agentFarmId": _string(observation.get("farm_id")) or agent_farm_id,
                    "agentObservationId": agent_observation_id,
                    "source": _string(observation.get("source")) or "field",
                    "observedAt": _timestamp_ms(observation.get("observed_at"), fallback=timestamp),
                    "content": _string(observation.get("content")) or "",
                    "paddockId": _string(observation.get("paddock_id")),
                    "herdId": _string(observation.get("herd_id")),
                    "metrics": (
                        observation.get("metrics")
                        if isinstance(observation.get("metrics"), dict)
                        else {}
                    ),
                    "mediaUrl": _string(observation.get("media_url")),
                    "tags": observation.get("tags") if isinstance(observation.get("tags"), list) else [],
                    "syncedAt": timestamp,
                }
            )
        )

    return [
        {"table": table, "records": records}
        for table, records in batches.items()
        if records
    ]


def build_farm_geo_sync_batches(
    summary: dict[str, Any],
    *,
    synced_at: int | None = None,
) -> list[dict[str, object]]:
    """Map farm geo state into Convex /sync batches for the Farm Map read model."""

    farm = summary.get("farm") if isinstance(summary.get("farm"), dict) else None
    if farm is None:
        return []

    agent_farm_id = _string(farm.get("id"))
    if agent_farm_id is None:
        return []

    timestamp = synced_at or _now_ms()
    batches: dict[str, list[dict[str, object]]] = {table: [] for table in SYNC_TABLE_ORDER}
    batches["farms"].append(
        _compact(
            {
                "agentFarmId": agent_farm_id,
                "name": _string(farm.get("name")) or "OpenPasture farm",
                "timezone": _string(farm.get("timezone")) or "UTC",
                "notes": _string(farm.get("notes")),
                "location": farm.get("location"),
                "boundary": farm.get("boundary"),
                "syncedAt": timestamp,
            }
        )
    )
    _append_land_unit_batches(batches, summary, agent_farm_id=agent_farm_id, timestamp=timestamp)

    return [
        {"table": table, "records": records}
        for table, records in batches.items()
        if records
    ]


def _post_sync_batch(
    sync_url: str,
    tenant_key: str,
    table: str,
    records: list[dict[str, object]],
) -> None:
    payload = json.dumps(
        {
            "tenantKey": tenant_key,
            "table": table,
            "records": records,
        }
    ).encode("utf-8")
    request = urllib_request.Request(
        sync_url,
        data=payload,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=10) as response:
        response.read()


def _post_sync_batches(batches: list[dict[str, object]]) -> dict[str, object] | None:
    sync_url = os.environ.get("CONVEX_SYNC_URL", "").strip()
    tenant_key = os.environ.get("CONVEX_SYNC_KEY", "").strip()
    if not sync_url or not tenant_key:
        return None
    if not batches:
        return {"status": "skipped", "reason": "no_farm_state"}

    posted: list[dict[str, object]] = []
    try:
        for batch in batches:
            table = str(batch["table"])
            records = batch["records"]
            if not isinstance(records, list):
                continue
            _post_sync_batch(sync_url, tenant_key, table, records)
            posted.append({"table": table, "records": len(records)})
    except Exception as exc:  # pragma: no cover - exact network errors vary by runtime
        return {
            "status": "error",
            "message": str(exc),
            "posted": posted,
        }

    return {"status": "ok", "posted": posted}


def sync_onboarding_summary(summary: dict[str, Any]) -> dict[str, object] | None:
    """Post onboarding state to OpenPasture Cloud when hosted sync is configured."""

    return _post_sync_batches(build_onboarding_sync_batches(summary))


def sync_farm_geo_state(farm_id: str) -> dict[str, object] | None:
    """Post the current farm boundary and land-unit geometry to OpenPasture Cloud."""

    store = get_store()
    farm = store.get_farm(farm_id)
    if farm is None:
        return {"status": "skipped", "reason": "farm_not_found"}

    summary = {
        "farm": serialize_value(farm),
        "land_units": serialize_value(store.list_land_units(farm_id)),
    }
    return _post_sync_batches(build_farm_geo_sync_batches(summary))
