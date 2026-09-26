from __future__ import annotations

from datetime import datetime, timedelta

from openpasture.domain import Farm, GeoFeature, GeoPoint, Herd, LandUnit, Observation
from openpasture.store.convex import ConvexStore


class FakeConvexStore(ConvexStore):
    def __init__(self):
        super().__init__("https://example.convex.cloud", "tenant_secret")
        self.records: dict[str, dict[str, dict[str, object]]] = {
            "farms": {},
            "landUnits": {},
            "herds": {},
            "observations": {},
            "decisions": {},
        }

    def _request(self, operation: str, args: dict[str, object] | None = None) -> object:
        payload = args or {}
        if operation == "farms.create":
            record = payload["record"]
            assert isinstance(record, dict)
            self.records["farms"][str(record["farmId"])] = record
            return record["farmId"]
        if operation == "farms.get":
            return self.records["farms"].get(str(payload["farmId"]))
        if operation == "farms.list":
            return list(self.records["farms"].values())
        if operation == "farms.update":
            self.records["farms"][str(payload["farmId"])].update(payload["patch"])  # type: ignore[arg-type]
            return True
        if operation == "landUnits.upsert":
            record = payload["record"]
            assert isinstance(record, dict)
            self.records["landUnits"][str(record["landUnitId"])] = record
            return record["landUnitId"]
        if operation == "landUnits.get":
            return self.records["landUnits"].get(str(payload["landUnitId"]))
        if operation == "landUnits.list":
            return [
                record
                for record in self.records["landUnits"].values()
                if record["farmId"] == payload["farmId"]
                and ("unitType" not in payload or record["unitType"] == payload["unitType"])
            ]
        if operation == "herds.create":
            record = payload["record"]
            assert isinstance(record, dict)
            self.records["herds"][str(record["herdId"])] = record
            return record["herdId"]
        if operation == "herds.list":
            return [record for record in self.records["herds"].values() if record["farmId"] == payload["farmId"]]
        if operation == "herds.updatePosition":
            self.records["herds"][str(payload["herdId"])]["currentPaddockId"] = payload["paddockId"]
            return True
        if operation == "observations.record":
            record = payload["record"]
            assert isinstance(record, dict)
            self.records["observations"][str(record["observationId"])] = record
            return record["observationId"]
        if operation == "observations.recent":
            cutoff = str(payload["observedAfter"])
            return [
                record
                for record in self.records["observations"].values()
                if record["farmId"] == payload["farmId"] and str(record["observedAt"]) >= cutoff
            ]
        if operation in {"decisions.create", "decisions.update"}:
            record = payload["record"]
            assert isinstance(record, dict)
            self.records["decisions"][str(record["decisionId"])] = record
            return record["decisionId"]
        if operation == "decisions.get":
            return self.records["decisions"].get(str(payload["decisionId"]))
        if operation == "decisions.list":
            rows = [
                record
                for record in self.records["decisions"].values()
                if record["farmId"] == payload["farmId"]
                and ("herdId" not in payload or record.get("herdId") == payload["herdId"])
                and ("status" not in payload or record["status"] == payload["status"])
            ]
            return sorted(rows, key=lambda record: str(record["windowStartsUtc"]), reverse=True)
        raise AssertionError(f"Unexpected operation: {operation}")


def test_convex_store_normalizes_cloud_url():
    store = ConvexStore("https://happy-goat-123.convex.cloud", "secret")

    assert store.deployment_url == "https://happy-goat-123.convex.site"
    assert store.store_url == "https://happy-goat-123.convex.site/store"


def test_convex_store_sends_bearer_key_and_operation_payload(monkeypatch):
    calls: list[dict[str, object]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"ok": True, "result": []}

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("openpasture.store.convex.httpx.post", fake_post)

    store = ConvexStore("https://happy-goat-123.convex.cloud", "opk_live_shared")

    assert store.list_farms() == []
    assert calls == [
        {
            "url": "https://happy-goat-123.convex.site/store",
            "json": {"operation": "farms.list", "args": {}},
            "headers": {"authorization": "Bearer opk_live_shared"},
            "timeout": 30.0,
        }
    ]


def test_convex_store_round_trips_core_gis_entities():
    store = FakeConvexStore()
    farm = Farm(
        id="farm_1",
        name="Willow Creek",
        timezone="America/Chicago",
        location=GeoPoint(longitude=-95.2, latitude=36.2),
    )
    geometry = GeoFeature.from_geojson(
        {
            "type": "Polygon",
            "coordinates": [[[-95.2, 36.2], [-95.1, 36.2], [-95.1, 36.3], [-95.2, 36.2]]],
        }
    )
    land_unit = LandUnit(
        id="pasture_north",
        farm_id=farm.id,
        unit_type="pasture",
        name="North Pasture",
        geometry=geometry,
        confidence=0.8,
        provenance={"source": "test"},
    )
    herd = Herd(id="herd_1", farm_id=farm.id, species="cattle", count=45, current_paddock_id=land_unit.id)
    observation = Observation(
        id="obs_1",
        farm_id=farm.id,
        source="field",
        observed_at=datetime.utcnow() - timedelta(hours=1),
        content="Residual is holding.",
        paddock_id=land_unit.id,
        herd_id=herd.id,
        tags=["field-note"],
    )

    assert store.create_farm(farm) == farm.id
    assert store.upsert_land_unit(land_unit) == land_unit.id
    assert store.create_herd(herd) == herd.id
    assert store.record_observation(observation) == observation.id

    assert store.get_farm(farm.id).location == farm.location  # type: ignore[union-attr]
    assert store.list_land_units(farm.id, unit_type="pasture")[0].id == land_unit.id
    assert store.get_herds(farm.id)[0].current_paddock_id == land_unit.id
    assert store.get_recent_observations(farm.id, days=7)[0].id == observation.id

    store.update_herd_position(herd.id, "pasture_south")
    assert store.get_herds(farm.id)[0].current_paddock_id == "pasture_south"


def test_convex_store_round_trips_multipolygon_farm_boundary():
    store = FakeConvexStore()
    boundary = GeoFeature.from_geojson(
        {
            "type": "MultiPolygon",
            "coordinates": [
                [[[-95.2, 36.2], [-95.1, 36.2], [-95.1, 36.3], [-95.2, 36.2]]],
                [[[-95.0, 36.0], [-94.9, 36.0], [-94.9, 36.1], [-95.0, 36.0]]],
            ],
        }
    )
    farm = Farm(id="farm_multi", name="Split Creek", timezone="America/Chicago", boundary=boundary)

    assert store.create_farm(farm) == farm.id
    loaded = store.get_farm(farm.id)

    assert loaded is not None
    assert loaded.boundary is not None
    assert loaded.boundary.to_geojson()["geometry"]["type"] == "MultiPolygon"


def test_convex_store_round_trips_grazing_decisions():
    from openpasture.domain import DecisionWindow, FarmerResponse, GrazingDecision

    store = FakeConvexStore()
    starts = datetime(2026, 9, 25, 6, 0).astimezone()
    decision = GrazingDecision(
        decision_id="gd_1",
        farm_id="farm_1",
        herd_id="herd_1",
        window=DecisionWindow(starts_at=starts, ends_at=starts + timedelta(days=1)),
        action="MOVE",
        to_land_unit_id="paddock_4",
        to_boundary={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        reasoning=["Paddock 4 has rested 38 days."],
    )
    store.create_decision(decision)
    decision.status = "modified"
    decision.farmer_response = FarmerResponse(at=starts, response="modified", note="Shift the west line.")
    store.update_decision(decision, event="modified")

    loaded = store.get_decision("gd_1")
    assert loaded is not None
    assert loaded.status == "modified"
    assert loaded.farmer_response.note == "Shift the west line."
    assert loaded.to_boundary == decision.to_boundary
    assert store.records["decisions"]["gd_1"]["payload"]["window"]["starts_at"] == starts.isoformat()
    assert [item.decision_id for item in store.list_decisions("farm_1", herd_id="herd_1")] == ["gd_1"]


def test_convex_store_reads_legacy_movement_decisions():
    store = FakeConvexStore()
    legacy = {
        "planId": "plan_1",
        "farmId": "farm_1",
        "herdId": "herd_1",
        "forDate": "2026-05-02",
        "action": "MOVE",
        "reasoning": ["Short."],
        "confidence": "medium",
        "sourcePaddockId": "p1",
        "targetPaddockId": "p2",
        "knowledgeEntryIds": [],
        "status": "pending",
        "createdAt": "2026-05-02T11:00:00",
    }
    decision = store._decision_from_record(legacy)

    assert decision is not None
    assert decision.decision_id == "plan_1"
    assert decision.status == "proposed"
    assert decision.to_land_unit_id == "p2"
