"""Grazing decision tools: the daily decision loop for each herd."""

from __future__ import annotations

from openpasture.context import (
    get_decision_engine,
    get_store,
    resolve_farm_id,
    schedule_farm_brief,
    set_active_farm_id,
)
from openpasture.briefing.engine import new_decision
from openpasture.domain import AUTONOMY_MODES, DecisionInputs, DecisionSettings, DecisionWindow
from openpasture.domain.clock import utc_now
from openpasture.tools._common import (
    json_response,
    optional_bool,
    optional_datetime,
    optional_float,
    optional_int,
    optional_mapping,
    optional_str,
    optional_str_list,
    optional_text_list,
    require_str,
)

_FARM = {"type": "string", "description": "Farm id. Optional when one farm is active."}
_HERD = {"type": "string", "description": "Herd id. Defaults to the farm's first herd."}
_GEOJSON = {"type": "object", "description": "GeoJSON Polygon in [longitude, latitude] order."}

COMPUTE_GRAZING_SIGNALS_SCHEMA = {
    "type": "object",
    "description": (
        "Grazing signals for a herd: grazing pressure from collars, rest days per paddock, forage from "
        "imagery and field notes, recovery trend, feed budget, weather and drought risk, and behavior."
    ),
    "properties": {
        "farm_id": _FARM,
        "herd_id": _HERD,
        "land_unit_ids": {"type": "array", "items": {"type": "string"}, "description": "Limit land reports to these units."},
    },
    "additionalProperties": True,
}

ASSEMBLE_DECISION_CONTEXT_SCHEMA = {
    "type": "object",
    "description": (
        "Everything the engine sees before today's decision for a herd: decision window, autonomy, where "
        "the herd is (and how we know), collar summary, land reports for the current paddock and candidates, "
        "recent field notes, decision history with outcomes, relevant knowledge, and signals."
    ),
    "properties": {"farm_id": _FARM, "herd_id": _HERD},
    "additionalProperties": True,
}

SUBMIT_GRAZING_DECISION_SCHEMA = {
    "type": "object",
    "description": (
        "Submit the agent's decision for a herd's current window: STAY, MOVE (with to_land_unit_id or "
        "to_boundary), or NEEDS_INFO (with uncertainty_request). The engine records it, applies the farmer's "
        "autonomy setting, and sends the boundary to the collars only when that setting allows."
    ),
    "properties": {
        "farm_id": _FARM,
        "herd_id": _HERD,
        "action": {"type": "string", "enum": ["STAY", "MOVE", "NEEDS_INFO"]},
        "reasoning": {
            "type": ["array", "string"],
            "items": {"type": "string"},
            "description": "Plain-language reasons, one per line.",
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "to_land_unit_id": {"type": "string", "description": "Paddock or section to move to."},
        "to_boundary": _GEOJSON,
        "from_land_unit_id": {"type": "string", "description": "Defaults to where the herd is recorded."},
        "uncertainty_request": {"type": "string", "description": "The single observation that would help most."},
        "inputs": {
            "type": "object",
            "description": "{land_report_ids, collar_summary_id, observation_ids, knowledge_entry_ids} the decision drew on.",
        },
        "exclusions": {"type": "array", "items": _GEOJSON, "description": "Areas inside the boundary to keep out of."},
        "transition": {
            "type": "object",
            "description": "{type: open_then_close|immediate, corridor: Polygon, close_after_minutes}.",
        },
    },
    "required": ["action", "reasoning"],
    "additionalProperties": True,
}

RESPOND_TO_DECISION_SCHEMA = {
    "type": "object",
    "description": (
        "Record the farmer's answer to a decision: approve, modify (with the farmer's boundary or "
        "land_unit_id), or reject. Approve or modify sends the boundary; reject stops a pending move. "
        "The engine's original stays on the record."
    ),
    "properties": {
        "decision_id": {"type": "string"},
        "response": {"type": "string", "enum": ["approve", "modify", "reject"]},
        "note": {"type": "string", "description": "The farmer's words. Always worth keeping."},
        "boundary": _GEOJSON,
        "land_unit_id": {"type": "string", "description": "For modify: send the herd here instead."},
    },
    "required": ["decision_id", "response"],
    "additionalProperties": True,
}

GET_DECISION_SCHEMA = {
    "type": "object",
    "description": "One decision from the record, with its boundary command and acknowledgements.",
    "properties": {"decision_id": {"type": "string"}},
    "required": ["decision_id"],
    "additionalProperties": True,
}

LIST_DECISIONS_SCHEMA = {
    "type": "object",
    "description": "Decisions from the record, newest first.",
    "properties": {
        "farm_id": _FARM,
        "herd_id": {"type": "string"},
        "status": {"type": "string"},
        "since": {"type": "string", "description": "ISO date or time; window start on or after."},
        "until": {"type": "string", "description": "ISO date or time; window start before."},
        "limit": {"type": "integer"},
    },
    "additionalProperties": True,
}

SET_AUTONOMY_SCHEMA = {
    "type": "object",
    "description": (
        "Set how far the engine may act without approval, for the farm or one herd: propose (default, every "
        "move waits), apply_unless_stopped (sent at send_time, or hold_minutes after deciding, unless stopped), "
        "or apply (sent when decided). Also sets the herd's decision window."
    ),
    "properties": {
        "farm_id": _FARM,
        "herd_id": {"type": "string", "description": "Omit to set the farm default."},
        "autonomy": {"type": "string", "enum": list(AUTONOMY_MODES)},
        "send_time": {"type": "string", "description": "HH:MM local time for apply_unless_stopped."},
        "hold_minutes": {"type": "integer", "description": "Minutes to wait when no send_time is set."},
        "window_hours": {"type": "integer", "description": "Decision window length. Default 24."},
        "window_start_time": {"type": "string", "description": "HH:MM local time each window starts."},
        "activation_threshold": {
            "type": "number",
            "description": "Share of collars (0-1] that must confirm before a boundary is active. Default 1.0.",
        },
    },
    "additionalProperties": True,
}

EVALUATE_DECISION_OUTCOME_SCHEMA = {
    "type": "object",
    "description": (
        "Evaluate what happened after a decision: whether the herd held the boundary, cue count, residual, "
        "and recovery notes. Written back to the decision record."
    ),
    "properties": {
        "decision_id": {"type": "string"},
        "residual_estimate_inches": {"type": "number", "description": "The farmer's residual reading, if known."},
        "notes": {"type": ["array", "string"], "items": {"type": "string"}},
    },
    "required": ["decision_id"],
    "additionalProperties": True,
}

RUN_DECISION_CYCLE_SCHEMA = {
    "type": "object",
    "description": (
        "Run the fallback decision cycle (heuristic advisor) for one herd or every herd: evaluate past "
        "decisions, send due moves, decide, apply autonomy, and save the morning brief. The scheduler calls this."
    ),
    "properties": {
        "farm_id": _FARM,
        "herd_id": {"type": "string", "description": "Omit to run every herd."},
        "force": {"type": "boolean", "description": "Decide again even if this window already has a decision."},
    },
    "additionalProperties": True,
}


def handle_compute_grazing_signals(args: dict[str, object]) -> str:
    farm_id = resolve_farm_id(args)
    context = get_decision_engine().assemble_context(
        farm_id,
        optional_str(args, "herd_id"),
        land_unit_ids=optional_str_list(args, "land_unit_ids") or None,
    )
    set_active_farm_id(farm_id)
    return json_response(
        status="ok",
        herd_id=context.herd.id if context.herd else None,
        current_land_unit_id=context.current_land_unit_id,
        position_source=context.position_source,
        land_report_ids={unit_id: report.report_id for unit_id, report in context.land_reports.items()},
        collar_summary=context.collar_summary,
        signals=context.signals,
    )


def handle_assemble_decision_context(args: dict[str, object]) -> str:
    farm_id = resolve_farm_id(args)
    context = get_decision_engine().assemble_context(farm_id, optional_str(args, "herd_id"), save_summary=True)
    set_active_farm_id(farm_id)
    return json_response(status="ok", context=context.to_dict())


def handle_submit_grazing_decision(args: dict[str, object]) -> str:
    farm_id = resolve_farm_id(args)
    engine = get_decision_engine()
    herd = engine.resolve_herd(farm_id, optional_str(args, "herd_id"))
    action = require_str(args, "action").upper()
    farm = get_store().get_farm(farm_id)
    if farm is None:
        raise ValueError(f"Farm '{farm_id}' does not exist.")
    raw_window = optional_mapping(args, "window")
    window = (
        DecisionWindow.from_dict(raw_window)
        if raw_window
        else engine.window_for(farm, engine.settings_for(farm_id, herd.id if herd else None), utc_now())
    )
    raw_inputs = optional_mapping(args, "inputs")
    boundary_options: dict[str, object] = {}
    if isinstance(args.get("exclusions"), list):
        boundary_options["exclusions"] = [item for item in args["exclusions"] if isinstance(item, dict)]  # type: ignore[union-attr]
    if transition := optional_mapping(args, "transition"):
        boundary_options["transition"] = transition

    decision = new_decision(
        farm_id=farm_id,
        herd_id=herd.id if herd else None,
        window=window,
        action=action,
        reasoning=optional_text_list(args, "reasoning"),
        confidence=optional_str(args, "confidence") or "medium",
        from_land_unit_id=optional_str(args, "from_land_unit_id") or (herd.current_paddock_id if herd else None),
        to_land_unit_id=optional_str(args, "to_land_unit_id"),
        to_boundary=optional_mapping(args, "to_boundary"),
        uncertainty_request=optional_str(args, "uncertainty_request"),
        inputs=DecisionInputs.from_dict(raw_inputs),
        boundary_options=boundary_options,
        decided_by=optional_str(args, "decided_by") or "agent",
    )
    result = engine.submit(decision)
    set_active_farm_id(farm_id)
    return json_response(status="ok", **result.to_dict())


def handle_respond_to_decision(args: dict[str, object]) -> str:
    decision_id = require_str(args, "decision_id")
    response = optional_str(args, "response") or optional_str(args, "status")
    if response is None:
        raise ValueError("'response' is required: approve, modify, or reject.")
    result = get_decision_engine().respond(
        decision_id,
        response,
        note=optional_str(args, "note") or optional_str(args, "feedback"),
        boundary=optional_mapping(args, "boundary"),
        land_unit_id=optional_str(args, "land_unit_id") or optional_str(args, "to_land_unit_id"),
    )
    set_active_farm_id(result.decision.farm_id)
    return json_response(status="ok", **result.to_dict())


def handle_get_decision(args: dict[str, object]) -> str:
    store = get_store()
    decision_id = require_str(args, "decision_id")
    decision = store.get_decision(decision_id)
    if decision is None:
        raise ValueError(f"Decision '{decision_id}' does not exist.")
    command = store.get_boundary_command(decision.boundary_command_id) if decision.boundary_command_id else None
    set_active_farm_id(decision.farm_id)
    return json_response(
        status="ok",
        decision=decision,
        boundary_command=command,
        acks=store.list_boundary_acks(command.command_id) if command else [],
    )


def handle_list_decisions(args: dict[str, object]) -> str:
    farm_id = resolve_farm_id(args)
    decisions = get_store().list_decisions(
        farm_id,
        herd_id=optional_str(args, "herd_id"),
        status=optional_str(args, "status"),
        since=optional_datetime(args, "since"),
        until=optional_datetime(args, "until"),
        limit=optional_int(args, "limit") or 50,
    )
    set_active_farm_id(farm_id)
    return json_response(status="ok", decisions=decisions, count=len(decisions))


def handle_set_autonomy(args: dict[str, object]) -> str:
    farm_id = resolve_farm_id(args)
    herd_id = optional_str(args, "herd_id")
    engine = get_decision_engine()
    if herd_id:
        engine.resolve_herd(farm_id, herd_id)
    settings = DecisionSettings(
        farm_id=farm_id,
        herd_id=herd_id,
        autonomy=(optional_str(args, "autonomy") or optional_str(args, "mode")),  # type: ignore[arg-type]
        send_time=optional_str(args, "send_time"),
        hold_minutes=optional_int(args, "hold_minutes"),
        window_hours=optional_int(args, "window_hours"),
        window_start_time=optional_str(args, "window_start_time"),
        activation_threshold=optional_float(args, "activation_threshold"),
    )
    effective = engine.save_settings(settings)
    schedule_farm_brief(farm_id)
    set_active_farm_id(farm_id)
    return json_response(status="ok", settings=effective)


def handle_evaluate_decision_outcome(args: dict[str, object]) -> str:
    decision = get_decision_engine().evaluate(
        require_str(args, "decision_id"),
        residual_estimate_inches=optional_float(args, "residual_estimate_inches"),
        notes=optional_text_list(args, "notes"),
    )
    set_active_farm_id(decision.farm_id)
    return json_response(status="ok", decision=decision, outcome=decision.outcome)


def handle_run_decision_cycle(args: dict[str, object]) -> str:
    store = get_store()
    farm_id = resolve_farm_id(args)
    engine = get_decision_engine()
    herd_id = optional_str(args, "herd_id")
    herds = [engine.resolve_herd(farm_id, herd_id)] if herd_id else store.get_herds(farm_id) or [None]
    results = []
    for herd in herds:
        result, context = engine.run_cycle(farm_id, herd.id if herd else None, force=bool(optional_bool(args, "force")))
        brief = engine.build_brief(result.decision, context)
        store.save_daily_brief(brief)
        results.append({**result.to_dict(), "brief": brief})
    set_active_farm_id(farm_id)
    return json_response(status="ok", results=results)
