from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from openpasture.context import get_collar_service, get_decision_engine, get_store
from openpasture.domain.clock import utc_now
from openpasture.domain.geo import point_in_geometry
from openpasture.tools.brief import handle_generate_morning_brief
from openpasture.tools.collar import handle_get_boundary_status, handle_record_collar_report
from openpasture.tools.decision import (
    handle_assemble_decision_context,
    handle_compute_grazing_signals,
    handle_evaluate_decision_outcome,
    handle_get_decision,
    handle_list_decisions,
    handle_respond_to_decision,
    handle_run_decision_cycle,
    handle_set_autonomy,
    handle_submit_grazing_decision,
)
from openpasture.tools.observe import handle_record_observation

pytestmark = pytest.mark.alpha

REASONS = ["Home is at roughly 4 inches of residual.", "North has rested and looks recovered."]
# A smaller piece of North: the farmer pulls the west line in.
FARMER_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [[[-92.398, 38.12], [-92.39, 38.12], [-92.39, 38.13], [-92.398, 38.13], [-92.398, 38.12]]],
}


def _move(**extra) -> dict:
    return json.loads(
        handle_submit_grazing_decision(
            {"herd_id": "herd_1", "action": "MOVE", "to_land_unit_id": "paddock_north", "reasoning": REASONS, **extra}
        )
    )


def test_propose_waits_for_the_farmer_then_sends_on_approval(collared_farm):
    submitted = _move(confidence="high")

    decision = submitted["decision"]
    assert decision["status"] == "proposed"
    assert decision["autonomy"] == "propose"
    assert decision["from_land_unit_id"] == "paddock_home"
    assert decision["to_boundary"]["type"] == "Polygon"
    assert submitted["boundary_command"] is None
    assert collared_farm.gateway.sent == []

    approved = json.loads(handle_respond_to_decision({"decision_id": decision["decision_id"], "response": "approve"}))
    assert approved["decision"]["status"] == "active"
    assert approved["decision"]["farmer_response"]["response"] == "approved"
    assert approved["boundary_command"]["version"] == 1
    assert approved["activation"]["active"] is True
    assert get_store().get_herds(collared_farm.farm_id)[0].current_paddock_id == "paddock_north"


def test_apply_sends_when_decided(collared_farm):
    handle_set_autonomy({"autonomy": "apply"})
    submitted = _move()

    assert submitted["decision"]["autonomy"] == "apply"
    assert submitted["decision"]["status"] == "active"
    assert submitted["boundary_command"]["collar_ids"] == list(collared_farm.collar_ids)
    assert len(collared_farm.gateway.sent) == 3


def test_apply_unless_stopped_sends_after_the_deadline(collared_farm):
    settings = json.loads(handle_set_autonomy({"autonomy": "apply_unless_stopped", "hold_minutes": 60}))["settings"]
    assert settings["autonomy_level"] == "farm"
    submitted = _move()
    decision_id = submitted["decision"]["decision_id"]
    assert submitted["decision"]["status"] == "proposed"
    assert submitted["decision"]["send_after"] is not None

    engine = get_decision_engine()
    engine.process_due(now=utc_now() + timedelta(minutes=30))
    assert get_store().get_decision(decision_id).status == "proposed"
    assert collared_farm.gateway.sent == []

    engine.process_due(now=utc_now() + timedelta(minutes=61))
    sent = get_store().get_decision(decision_id)
    assert sent.status == "active"
    assert sent.farmer_response is None  # the autonomy setting sent it


def test_apply_unless_stopped_does_not_send_when_rejected(collared_farm):
    handle_set_autonomy({"herd_id": "herd_1", "autonomy": "apply_unless_stopped", "hold_minutes": 60})
    decision_id = _move()["decision"]["decision_id"]

    stopped = json.loads(
        handle_respond_to_decision({"decision_id": decision_id, "response": "reject", "note": "Too wet to move today."})
    )
    assert stopped["decision"]["status"] == "rejected"
    get_decision_engine().process_due(now=utc_now() + timedelta(hours=3))

    record = get_store().get_decision(decision_id)
    assert record.status == "rejected"
    assert record.farmer_response.note == "Too wet to move today."
    assert collared_farm.gateway.sent == []


def test_modified_decision_sends_the_farmer_boundary_and_keeps_the_original(collared_farm):
    decision = _move()["decision"]
    modified = json.loads(
        handle_respond_to_decision(
            {
                "decision_id": decision["decision_id"],
                "response": "modify",
                "note": "Shift the west line in, the wet spot is bigger than it looks.",
                "boundary": FARMER_BOUNDARY,
            }
        )
    )

    record = modified["decision"]
    assert record["farmer_response"]["response"] == "modified"
    assert record["farmer_response"]["boundary"] == FARMER_BOUNDARY
    assert record["to_boundary"] == decision["to_boundary"]  # the engine's original stays on the record
    assert modified["boundary_command"]["boundary"] == FARMER_BOUNDARY
    assert record["status"] == "active"
    sent_ring = collared_farm.gateway.sent[0]["boundary"]
    assert [-92.398, 38.12] in sent_ring


def test_stay_skips_the_send_steps(collared_farm):
    handle_set_autonomy({"autonomy": "apply"})
    submitted = json.loads(
        handle_submit_grazing_decision({"action": "STAY", "reasoning": ["Plenty of residual left in Home."]})
    )

    assert submitted["decision"]["status"] == "proposed"
    assert submitted["boundary_command"] is None
    approved = json.loads(handle_respond_to_decision({"decision_id": submitted["decision"]["decision_id"], "response": "approve"}))
    assert approved["decision"]["status"] == "approved"
    assert collared_farm.gateway.sent == []


def test_needs_info_must_ask_one_question(collared_farm):
    with pytest.raises(ValueError, match="uncertainty_request"):
        handle_submit_grazing_decision({"action": "NEEDS_INFO", "reasoning": ["Not sure."]})

    submitted = json.loads(
        handle_submit_grazing_decision(
            {
                "action": "NEEDS_INFO",
                "reasoning": ["No field note since the rain."],
                "uncertainty_request": "How firm is the ground on the low side of Home?",
                "confidence": "low",
            }
        )
    )
    assert submitted["decision"]["uncertainty_request"].startswith("How firm")


def test_move_needs_a_target(collared_farm):
    with pytest.raises(ValueError, match="to_land_unit_id or to_boundary"):
        handle_submit_grazing_decision({"action": "MOVE", "reasoning": REASONS})


def test_herd_override_beats_farm_autonomy(collared_farm):
    handle_set_autonomy({"autonomy": "apply"})
    herd = json.loads(handle_set_autonomy({"herd_id": "herd_1", "autonomy": "propose"}))["settings"]

    assert herd["autonomy"] == "propose" and herd["autonomy_level"] == "herd"
    assert _move()["decision"]["status"] == "proposed"


def test_rejecting_after_send_is_recorded_not_undone(collared_farm):
    handle_set_autonomy({"autonomy": "apply"})
    decision_id = _move()["decision"]["decision_id"]
    result = json.loads(handle_respond_to_decision({"decision_id": decision_id, "response": "reject"}))

    assert result["decision"]["status"] == "active"
    assert result["decision"]["farmer_response"]["response"] == "rejected"
    assert "already sent" in result["message"]


def test_signals_and_context_tools(collared_farm):
    signals = json.loads(handle_compute_grazing_signals({"herd_id": "herd_1"}))
    assert signals["position_source"] == "collar"
    assert signals["current_land_unit_id"] == "paddock_home"
    assert signals["signals"]["rest_days"]["paddock_home"] == 0.0
    assert signals["signals"]["forage"]["paddock_north"]["source"] == "imagery"
    assert signals["signals"]["grazing_pressure"]["paddock_home"]["share_of_time"] == 1.0
    assert signals["signals"]["feed_budget_days_current"] is not None
    assert signals["signals"]["behavior"]["grazing_share"] is not None

    context = json.loads(handle_assemble_decision_context({}))["context"]
    assert context["settings"]["autonomy"] == "propose"
    assert set(context["land_reports"]) == {"paddock_home", "paddock_north"}
    assert context["collar_summary"]["fix_count"] == 12
    assert context["window"]["starts_at"].endswith(("-05:00", "-06:00"))


def test_full_cycle_end_to_end(collared_farm):
    handle_set_autonomy({"autonomy": "apply"})
    handle_record_observation(
        {
            "source": "field",
            "content": "Home is getting short and muddy near the water point.",
            "paddock_id": "paddock_home",
            "herd_id": "herd_1",
            "metrics": {"residual_inches": 4},
        }
    )

    cycle = json.loads(handle_run_decision_cycle({}))["results"][0]
    decision = cycle["decision"]
    assert decision["action"] == "MOVE"
    assert decision["decided_by"] == "heuristic"
    assert decision["to_land_unit_id"] == "paddock_north"
    assert decision["status"] == "active"
    assert decision["inputs"]["land_report_ids"]
    assert decision["inputs"]["collar_summary_id"].startswith("cs_")
    assert decision["inputs"]["observation_ids"]
    assert cycle["brief"]["decision"]["decision_id"] == decision["decision_id"]
    assert "MOVE" in cycle["brief"]["summary"]

    status = json.loads(handle_get_boundary_status({"decision_id": decision["decision_id"]}))
    assert status["activation"]["active"] is True
    assert status["unconfirmed_collars"] == []

    # The morning brief wraps the same decision instead of deciding again.
    brief = json.loads(handle_generate_morning_brief({}))["brief"]
    assert brief["decision"]["decision_id"] == decision["decision_id"]

    # The herd walks into North and the collars report from there.
    activated_at = datetime.fromisoformat(status["command"]["activated_at"])
    for collar_id in collared_farm.collar_ids:
        report = collared_farm.gateway.simulate_report(collar_id, collared_farm.north, start=activated_at, count=1)
        assert all(point_in_geometry(fix["point"], collared_farm.north) for fix in report["fixes"])
        handle_record_collar_report({"report": report})

    evaluated = json.loads(
        handle_evaluate_decision_outcome(
            {"decision_id": decision["decision_id"], "notes": ["Animals settled quickly."]}
        )
    )["decision"]
    assert evaluated["status"] == "evaluated"
    assert evaluated["outcome"]["herd_held_boundary"] is True
    assert evaluated["outcome"]["cue_count"] == 0
    assert evaluated["outcome"]["residual_estimate_inches"] is None  # the note predates the decision
    assert "Animals settled quickly." in evaluated["outcome"]["notes"]

    listed = json.loads(handle_list_decisions({"herd_id": "herd_1", "status": "evaluated"}))
    assert [item["decision_id"] for item in listed["decisions"]] == [decision["decision_id"]]
    fetched = json.loads(handle_get_decision({"decision_id": decision["decision_id"]}))
    assert len(fetched["acks"]) == 3

    # Next window: the collars place the herd in North and a new decision is made.
    tomorrow = utc_now() + timedelta(days=1, hours=1)
    result, context = get_decision_engine().run_cycle(collared_farm.farm_id, "herd_1", now=tomorrow)
    assert context is not None
    assert context.current_land_unit_id == "paddock_north"
    assert result.decision.decision_id != decision["decision_id"]
    assert result.decision.from_land_unit_id == "paddock_north"


def test_prior_decisions_are_evaluated_on_the_next_cycle(collared_farm):
    first, _ = get_decision_engine().run_cycle(collared_farm.farm_id, "herd_1")
    later = utc_now() + timedelta(days=2)
    get_decision_engine().run_cycle(collared_farm.farm_id, "herd_1", now=later)

    assert get_store().get_decision(first.decision.decision_id).status == "evaluated"


def test_list_decisions_filters_by_date(collared_farm):
    _move()
    today = utc_now().date()
    assert json.loads(handle_list_decisions({"since": (today - timedelta(days=2)).isoformat()}))["count"] == 1
    assert json.loads(handle_list_decisions({"until": (today - timedelta(days=2)).isoformat()}))["count"] == 0


def test_collar_service_is_shared_with_the_engine(collared_farm):
    assert get_decision_engine().collars.gateway is get_collar_service().gateway
