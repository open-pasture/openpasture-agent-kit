"""Collar tools: position reports, herd positions, and boundary status."""

from __future__ import annotations

from datetime import timedelta

from openpasture.context import (
    get_collar_service,
    get_decision_engine,
    get_store,
    resolve_farm_id,
    set_active_farm_id,
)
from openpasture.domain.clock import utc_now
from openpasture.tools._common import json_response, optional_int, optional_str

RECORD_COLLAR_REPORT_SCHEMA = {
    "type": "object",
    "description": (
        "Ingest one collar's position report (fixes, cues, battery, boundary_version) and any boundary "
        "acknowledgements. Accepts the OpenCollar wire shape or the contract shape. Pass herd_id the first "
        "time a collar reports so it is registered to the herd."
    ),
    "properties": {
        "farm_id": {"type": "string", "description": "Optional when one farm is active."},
        "herd_id": {"type": "string", "description": "Herd the collar belongs to. Needed for a new collar."},
        "report": {
            "type": "object",
            "description": "PositionReport: {collar_id, boundary_version, fixes: [{at, point, accuracy_m|accuracy_meters, sats, activity}], cues: [{at, level, margin_m, type, point}], battery}.",
        },
        "collar_id": {"type": "string"},
        "fixes": {"type": "array"},
        "cues": {"type": "array"},
        "battery": {"type": "number"},
        "boundary_version": {"type": "integer"},
        "acks": {
            "type": "array",
            "description": "Acknowledgements: [{command_id, version, status: received|applied|rejected, at|received_at, reason, collar_id}].",
        },
    },
    "additionalProperties": True,
}

GET_HERD_POSITIONS_SCHEMA = {
    "type": "object",
    "description": "Latest collar fix per collar and the current collar summary for a herd.",
    "properties": {
        "farm_id": {"type": "string", "description": "Optional when one farm is active."},
        "herd_id": {"type": "string", "description": "Defaults to the farm's first herd."},
        "hours": {"type": "integer", "description": "Look-back in hours. Defaults to the herd's decision window."},
    },
    "additionalProperties": True,
}

GET_BOUNDARY_STATUS_SCHEMA = {
    "type": "object",
    "description": (
        "A boundary command with every collar acknowledgement, whether it is active, and which collars "
        "have not confirmed. Pass command_id, decision_id, or herd_id for the herd's latest command."
    ),
    "properties": {
        "command_id": {"type": "string"},
        "decision_id": {"type": "string"},
        "herd_id": {"type": "string"},
        "farm_id": {"type": "string"},
    },
    "additionalProperties": True,
}


def handle_record_collar_report(args: dict[str, object]) -> str:
    farm_id = resolve_farm_id(args)
    herd_id = optional_str(args, "herd_id")
    service = get_collar_service()
    payload = args.get("report") if isinstance(args.get("report"), dict) else args
    collar_id = payload.get("collar_id") if isinstance(payload, dict) else None  # type: ignore[union-attr]

    ingest = None
    if collar_id:
        report = service.gateway.parse_position_report(payload)  # type: ignore[arg-type]
        ingest = service.ingest_report(report, farm_id=farm_id, herd_id=herd_id)

    raw_acks = args.get("acks") or (payload.get("acks") if isinstance(payload, dict) else None)  # type: ignore[union-attr]
    acks = [
        service.gateway.parse_ack(item, collar_id=str(collar_id) if collar_id else None)
        for item in raw_acks or []  # type: ignore[union-attr]
        if isinstance(item, dict)
    ]
    if not ingest and not acks:
        raise ValueError("Pass a position report (with collar_id) or acks.")
    updated = service.record_acks(acks) if acks else []
    activated = get_decision_engine().handle_acks(updated) if updated else []
    set_active_farm_id(farm_id)
    return json_response(
        status="ok",
        ingest=ingest,
        acks_recorded=len(acks),
        boundary_updates=[
            {"command_id": command.command_id, "status": command.status, "activation": activation.to_dict()}
            for command, activation in updated
        ],
        decisions_activated=[decision.decision_id for decision in activated],
    )


def handle_get_herd_positions(args: dict[str, object]) -> str:
    store = get_store()
    farm_id = resolve_farm_id(args)
    engine = get_decision_engine()
    herd = engine.resolve_herd(farm_id, optional_str(args, "herd_id"))
    if herd is None:
        raise ValueError(f"Farm '{farm_id}' has no herds yet.")
    settings = engine.settings_for(farm_id, herd.id)
    hours = optional_int(args, "hours") or settings.window_hours
    now = utc_now()
    service = get_collar_service()
    summary = service.summarize(farm_id, herd.id, now - timedelta(hours=hours), now)
    set_active_farm_id(farm_id)
    return json_response(
        status="ok",
        herd=herd,
        collars=store.list_collars(farm_id, herd.id),
        latest_fixes=service.latest_fixes(herd.id, since=now - timedelta(hours=hours)),
        collar_summary=summary,
        current_land_unit_id=(summary.dominant_land_unit_id if summary and summary.dominant_land_unit_id else herd.current_paddock_id),
        position_source="collar" if summary and summary.dominant_land_unit_id else "farm_record",
        active_boundary=service.active_command(herd.id),
    )


def handle_get_boundary_status(args: dict[str, object]) -> str:
    store = get_store()
    service = get_collar_service()
    command = None
    if command_id := optional_str(args, "command_id"):
        command = store.get_boundary_command(command_id)
    elif decision_id := optional_str(args, "decision_id"):
        decision = store.get_decision(decision_id)
        if decision is None:
            raise ValueError(f"Decision '{decision_id}' does not exist.")
        if decision.boundary_command_id:
            command = store.get_boundary_command(decision.boundary_command_id)
        if command is None:
            return json_response(status="ok", decision_id=decision_id, command=None, message="No boundary was sent for this decision.")
    else:
        farm_id = resolve_farm_id(args)
        herd = get_decision_engine().resolve_herd(farm_id, optional_str(args, "herd_id"))
        command = service.latest_command(herd.id) if herd else None
    if command is None:
        return json_response(status="ok", command=None, message="No boundary command found.")
    status = service.boundary_status(command)
    refreshed = status["command"]
    get_decision_engine().handle_acks(
        [(refreshed, service.refresh(refreshed))]  # type: ignore[arg-type]
    )
    return json_response(status="ok", **status)
