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
        raise AssertionError(f"Unexpected operation: {operation}")


def test_convex_store_normalizes_cloud_url():
    store = ConvexStore("https://happy-goat-123.convex.cloud", "secret")

    assert store.deployment_url == "https://happy-goat-123.convex.site"
    assert store.store_url == "https://happy-goat-123.convex.site/store"


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
