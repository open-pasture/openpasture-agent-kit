from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from openpasture.collars import BoundaryTranslationError, CollarService, HttpCollarGateway, SimulatedCollarGateway
from openpasture.collars.wire import parse_position_report, parse_wire_ack, to_wire_boundaries
from openpasture.context import get_collar_service, get_store
from openpasture.domain import BoundaryCommand, BoundaryTransition, PositionReport, boundary_activation
from openpasture.domain.geo import point_in_geometry
from openpasture.tools.collar import (
    handle_get_boundary_status,
    handle_get_herd_positions,
    handle_record_collar_report,
)

NOW = datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc)
# Same paddocks as the collared_farm fixture.
HOME = {"type": "Polygon", "coordinates": [[[-92.41, 38.12], [-92.40, 38.12], [-92.40, 38.13], [-92.41, 38.13], [-92.41, 38.12]]]}
NORTH = {"type": "Polygon", "coordinates": [[[-92.40, 38.12], [-92.39, 38.12], [-92.39, 38.13], [-92.40, 38.13], [-92.40, 38.12]]]}
COLLAR_IDS = ("oc_0012", "oc_0013", "oc_0014")


def _command(boundary=NORTH, **overrides) -> BoundaryCommand:
    values = dict(
        command_id="bc_test",
        decision_id=None,
        farm_id="farm",
        herd_id="herd",
        collar_ids=["oc_1", "oc_2"],
        version=42,
        effective_at=NOW,
        boundary=boundary,
    )
    values.update(overrides)
    return BoundaryCommand(**values)


def test_immediate_command_is_one_unclosed_ring():
    wire = to_wire_boundaries(_command())

    assert len(wire) == 1
    assert wire[0]["version"] == 42
    assert wire[0]["effective_at"] == "2026-09-25T12:30:00Z"
    assert wire[0]["boundary"] == [[-92.4, 38.12], [-92.39, 38.12], [-92.39, 38.13], [-92.4, 38.13]]


def test_open_then_close_expands_to_two_versions():
    command = _command(transition=BoundaryTransition(type="open_then_close", close_after_minutes=90))
    wire = to_wire_boundaries(command, previous_boundary=HOME)

    assert [item["version"] for item in wire] == [42, 43]
    assert wire[1]["effective_at"] == "2026-09-25T14:00:00Z"
    combined = {"type": "Polygon", "coordinates": [wire[0]["boundary"] + [wire[0]["boundary"][0]]]}
    # The open phase covers both paddocks; the close phase is the new paddock alone.
    assert point_in_geometry([-92.405, 38.125], combined)
    assert point_in_geometry([-92.395, 38.125], combined)
    assert len(wire[1]["boundary"]) == 4


def test_transition_without_a_path_is_refused():
    far = {"type": "Polygon", "coordinates": [[[-92.30, 38.12], [-92.29, 38.12], [-92.29, 38.13], [-92.30, 38.13]]]}
    command = _command(boundary=far, transition=BoundaryTransition(type="open_then_close"))

    with pytest.raises(BoundaryTranslationError, match="corridor"):
        to_wire_boundaries(command, previous_boundary=HOME)


def test_exclusions_are_cut_or_refused():
    pond_edge = {"type": "Polygon", "coordinates": [[[-92.392, 38.124], [-92.389, 38.124], [-92.389, 38.126], [-92.392, 38.126]]]}
    cut = to_wire_boundaries(_command(exclusions=[pond_edge]))[0]["boundary"]
    ring = {"type": "Polygon", "coordinates": [cut + [cut[0]]]}
    assert not point_in_geometry([-92.3905, 38.125], ring)
    assert point_in_geometry([-92.395, 38.125], ring)

    hole = {"type": "Polygon", "coordinates": [[[-92.396, 38.124], [-92.394, 38.124], [-92.394, 38.126]]]}
    with pytest.raises(BoundaryTranslationError, match="cannot enforce holes"):
        to_wire_boundaries(_command(exclusions=[hole]))


def test_vertex_budget_is_enforced():
    circle = [
        [-92.395 + 0.004 * math.cos(2 * math.pi * i / 70), 38.125 + 0.004 * math.sin(2 * math.pi * i / 70)]
        for i in range(70)
    ]
    with pytest.raises(BoundaryTranslationError, match="at most 64"):
        to_wire_boundaries(_command(boundary={"type": "Polygon", "coordinates": [circle]}))


def test_parse_wire_report_and_ack_into_contract_names():
    report = parse_position_report(
        {
            "collar_id": "oc_0012",
            "boundary_version": 42,
            "fixes": [{"at": "2026-09-25T10:40:00Z", "point": [-92.4051, 38.1244], "accuracy_m": 1.8, "sats": 9}],
            "cues": [{"at": "2026-09-25T10:12:00Z", "level": 2, "margin_m": -1.4}],
            "battery": 0.81,
        }
    )
    assert report.fixes[0].accuracy_meters == 1.8
    assert report.fixes[0].sats == 9
    assert report.fixes[0].boundary_version == 42
    assert report.cues[0].margin_meters == -1.4 and report.cues[0].level == 2
    assert report.battery == 0.81

    ack = parse_wire_ack({"command_id": "bc_1", "version": 42, "status": "applied", "at": "2026-09-25T12:30:04Z"}, collar_id="oc_0012")
    assert ack.to_dict() == {
        "command_id": "bc_1",
        "collar_id": "oc_0012",
        "version": 42,
        "status": "applied",
        "received_at": "2026-09-25T12:30:04+00:00",
    }


def test_activation_needs_applied_not_just_received():
    command = _command()
    from openpasture.domain import BoundaryAck

    received = [BoundaryAck("bc_test", "oc_1", 42, "received", NOW), BoundaryAck("bc_test", "oc_2", 42, "applied", NOW)]
    assert boundary_activation(command, received).active is False
    command.activation_threshold = 0.5
    activation = boundary_activation(command, received)
    assert activation.active is True
    assert activation.unconfirmed_collar_ids == ["oc_1"]


def _issue(service: CollarService, farm, boundary=NORTH, **kwargs):
    return service.issue_boundary(farm_id=farm.farm_id, herd_id=farm.herd_id, boundary=boundary, land_unit_id="paddock_north", **kwargs)


def test_versions_increase_per_herd_including_transitions(collared_farm):
    service = get_collar_service()
    first, activation = _issue(service, collared_farm)
    assert first.version == 1 and first.status == "active" and activation.active
    assert set(activation.confirmed_collar_ids) == set(COLLAR_IDS)

    second, _ = _issue(
        service,
        collared_farm,
        boundary=HOME,
        transition=BoundaryTransition(type="open_then_close", close_after_minutes=90),
    )
    assert (second.version, second.final_version) == (2, 3)
    # Open phase applied now, close phase staged for later.
    statuses = {(ack.version, ack.status) for ack in get_store().list_boundary_acks(second.command_id)}
    assert statuses == {(2, "applied"), (3, "received")}
    assert second.status == "active"

    third, _ = _issue(service, collared_farm)
    assert third.version == 4

    # The simulated firmware ignores anything not newer than what it holds.
    stale = to_wire_boundaries(_command(command_id="bc_stale", version=2, collar_ids=["oc_0012"]))
    acks = collared_farm.gateway.send_boundary(_command(command_id="bc_stale", version=2, collar_ids=["oc_0012"]), stale)
    assert acks[0].status == "rejected" and "not newer" in (acks[0].reason or "")


def test_unconfirmed_collars_are_surfaced_and_later_acks_activate(collared_farm):
    collared_farm.gateway.offline_collar_ids.add("oc_0014")
    command, activation = _issue(get_collar_service(), collared_farm)

    assert command.status == "sent"
    assert activation.active is False
    status = json.loads(handle_get_boundary_status({"command_id": command.command_id}))
    assert status["activation"]["active"] is False
    assert [item["collar_id"] for item in status["unconfirmed_collars"]] == ["oc_0014"]
    assert status["unconfirmed_collars"][0]["last_seen_at"] is not None

    # The late collar reports in over the wire.
    result = json.loads(
        handle_record_collar_report(
            {
                "report": {"collar_id": "oc_0014", "fixes": [], "cues": []},
                "acks": [{"command_id": command.command_id, "version": command.version, "status": "applied", "at": NOW.isoformat()}],
            }
        )
    )
    assert result["boundary_updates"][0]["status"] == "active"
    assert get_store().get_boundary_command(command.command_id).status == "active"


def test_activation_threshold_allows_partial_confirmation(collared_farm):
    collared_farm.gateway.offline_collar_ids.add("oc_0014")
    command, activation = _issue(get_collar_service(), collared_farm, activation_threshold=0.6)

    assert command.status == "active"
    assert activation.unconfirmed_collar_ids == ["oc_0014"]


def test_rejecting_collars_are_recorded_with_reason(collared_farm):
    collared_farm.gateway.rejecting_collar_ids.update({collar_id: "Ring crosses itself." for collar_id in COLLAR_IDS})
    command, activation = _issue(get_collar_service(), collared_farm)

    assert command.status == "rejected"
    assert activation.rejected["oc_0012"] == "Ring crosses itself."


def test_untranslatable_command_is_saved_as_rejected(collared_farm):
    hole = {"type": "Polygon", "coordinates": [[[-92.396, 38.124], [-92.394, 38.124], [-92.394, 38.126]]]}
    command, _ = _issue(get_collar_service(), collared_farm, exclusions=[hole])

    assert command.status == "rejected"
    assert "holes" in (command.error or "")
    assert collared_farm.gateway.sent == []


def test_ingest_assigns_land_units_and_prunes_old_fixes(collared_farm):
    store = get_store()
    now = datetime.now(timezone.utc)
    service = CollarService(store, SimulatedCollarGateway(), retention_days=1)
    report = service.gateway.parse_position_report(
        {
            "collar_id": "oc_0012",
            "fixes": [
                {"at": (now - timedelta(days=3)).isoformat(), "point": [-92.395, 38.125]},
                {"at": (now - timedelta(minutes=5)).isoformat(), "point": [-92.395, 38.125], "activity": "grazing"},
            ],
            "battery": 0.5,
        }
    )
    result = service.ingest_report(report, farm_id=collared_farm.farm_id)

    assert result["herd_id"] == "herd_1"  # already registered to the herd
    assert result["land_unit_fix_counts"] == {"paddock_north": 2}
    fixes = store.list_position_fixes("herd_1", now - timedelta(days=5))
    assert all(fix.at > now - timedelta(days=1) for fix in fixes)
    assert store.get_collar("oc_0012").battery == 0.5


def test_unknown_collar_needs_a_herd(collared_farm):
    with pytest.raises(ValueError, match="Pass herd_id"):
        get_collar_service().ingest_report(PositionReport(collar_id="oc_new"), farm_id=collared_farm.farm_id)


def test_get_herd_positions_reports_collar_location(collared_farm):
    result = json.loads(handle_get_herd_positions({"herd_id": "herd_1"}))

    assert result["position_source"] == "collar"
    assert result["current_land_unit_id"] == "paddock_home"
    assert len(result["latest_fixes"]) == 3
    assert result["collar_summary"]["fix_count"] == 12
    assert result["collar_summary"]["dominant_land_unit_id"] == "paddock_home"


def test_http_gateway_posts_wire_boundaries(collared_farm):
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append({"url": str(request.url), "auth": request.headers.get("authorization"), "body": body})
        wire = body["boundaries"][0]
        return httpx.Response(
            200,
            json={
                "acks": [
                    {"collar_id": collar_id, "command_id": wire["command_id"], "version": wire["version"], "status": "applied", "at": "2026-09-25T12:30:04Z"}
                    for collar_id in body["collar_ids"]
                ]
            },
        )

    gateway = HttpCollarGateway(
        "https://collars.example/api/", token="secret", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    service = CollarService(get_store(), gateway)
    command, activation = service.issue_boundary(
        farm_id=collared_farm.farm_id, herd_id="herd_1", boundary=NORTH, land_unit_id="paddock_north"
    )

    assert seen[0]["url"] == "https://collars.example/api/boundaries"
    assert seen[0]["auth"] == "Bearer secret"
    assert seen[0]["body"]["boundaries"][0]["boundary"][0] == [-92.4, 38.12]
    assert command.status == "active" and activation.active


def test_http_gateway_failure_marks_command_failed(collared_farm):
    gateway = HttpCollarGateway(
        "https://collars.example", client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    )
    command, _ = CollarService(get_store(), gateway).issue_boundary(
        farm_id=collared_farm.farm_id, herd_id="herd_1", boundary=NORTH
    )

    assert command.status == "failed"
    assert "Collar gateway request failed" in (command.error or "")
