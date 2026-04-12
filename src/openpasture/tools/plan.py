"""Movement planning and feedback tools."""

from __future__ import annotations

from datetime import date, datetime

from openpasture.domain import MovementDecision
from openpasture.runtime import get_store, set_active_farm_id
from openpasture.tools._common import (
    json_response,
    make_id,
    optional_str,
    optional_str_list,
    parse_date_value,
    require_str,
)


MOVEMENT_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "farm_id": {"type": "string"},
        "for_date": {"type": "string"},
        "action": {"type": "string"},
        "herd_id": {"type": "string"},
        "target_paddock_id": {"type": "string"},
    },
    "required": ["farm_id", "for_date"],
    "additionalProperties": True,
}

APPROVE_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "plan_id": {"type": "string"},
        "status": {"type": "string"},
        "feedback": {"type": "string"},
        "herd_id": {"type": "string"},
        "target_paddock_id": {"type": "string"},
    },
    "required": ["plan_id", "status"],
    "additionalProperties": True,
}


def handle_movement_decision(args: dict[str, object]) -> str:
    """Create or update the current movement recommendation."""
    store = get_store()
    farm_id = require_str(args, "farm_id")
    action = optional_str(args, "action") or "NEEDS_INFO"
    reasoning = optional_str_list(args, "reasoning")
    plan = MovementDecision(
        id=optional_str(args, "plan_id") or make_id("plan"),
        farm_id=farm_id,
        herd_id=optional_str(args, "herd_id"),
        for_date=parse_date_value(args.get("for_date"), default=date.today()),
        action=action,
        reasoning=reasoning or ["Manual plan recorded from tool input."],
        confidence=optional_str(args, "confidence") or "medium",
        source_paddock_id=optional_str(args, "source_paddock_id"),
        target_paddock_id=optional_str(args, "target_paddock_id"),
        knowledge_entry_ids=optional_str_list(args, "knowledge_entry_ids"),
        status=optional_str(args, "status") or "pending",
        farmer_feedback=optional_str(args, "farmer_feedback"),
        created_at=datetime.utcnow(),
    )
    store.create_plan(plan)
    set_active_farm_id(farm_id)
    return json_response(status="ok", plan=plan)


def handle_approve_plan(args: dict[str, object]) -> str:
    """Record farmer approval, rejection, or modification feedback."""
    store = get_store()
    plan_id = require_str(args, "plan_id")
    status = require_str(args, "status")
    feedback = optional_str(args, "feedback")
    store.update_plan_status(plan_id=plan_id, status=status, feedback=feedback)

    plan = store.get_plan(plan_id)
    if plan is None:
        raise ValueError(f"Plan '{plan_id}' does not exist.")

    herd_id = optional_str(args, "herd_id") or plan.herd_id
    target_paddock_id = optional_str(args, "target_paddock_id") or plan.target_paddock_id
    if status == "approved" and herd_id and target_paddock_id:
        store.update_herd_position(herd_id=herd_id, paddock_id=target_paddock_id)

    set_active_farm_id(plan.farm_id)
    return json_response(status="ok", plan=store.get_plan(plan_id))
