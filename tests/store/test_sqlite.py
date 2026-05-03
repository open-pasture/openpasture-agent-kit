from __future__ import annotations

from datetime import date, datetime

from openpasture.domain import (
    Animal,
    DataPipeline,
    Farm,
    FarmerAction,
    GeoFeature,
    GeoPoint,
    GeoPolygon,
    Herd,
    LandUnit,
    MovementDecision,
    Observation,
)
from openpasture.manifest import build_profile_manifest
from openpasture.store.sqlite import SQLiteStore


def build_store(tmp_path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / ".openpasture")
    store.bootstrap()
    return store


def test_sqlite_store_round_trips_core_entities(tmp_path):
    store = build_store(tmp_path)
    farm = Farm(
        id="farm_1",
        name="Willow Creek",
        timezone="America/Chicago",
        location=GeoPoint(longitude=-95.2, latitude=36.2),
        boundary=GeoPolygon(
            coordinates=[
                GeoPoint(-95.2, 36.2),
                GeoPoint(-95.3, 36.2),
                GeoPoint(-95.3, 36.3),
            ]
        ),
    )
    paddock = LandUnit(
        id="paddock_1",
        farm_id=farm.id,
        unit_type="paddock",
        name="North 40",
        geometry=GeoFeature.from_geojson(
            {
                "type": "Polygon",
                "coordinates": [[[-95.21, 36.21], [-95.22, 36.21], [-95.22, 36.22], [-95.21, 36.21]]],
            }
        ),
        status="resting",
    )
    herd = Herd(
        id="herd_1",
        farm_id=farm.id,
        species="cattle",
        count=45,
        current_paddock_id=paddock.id,
    )
    observation = Observation(
        id="obs_1",
        farm_id=farm.id,
        source="manual",
        observed_at=datetime.utcnow(),
        content="Residual is getting tight and animals are starting to hunt.",
        paddock_id=paddock.id,
        herd_id=herd.id,
        metrics={"residual_inches": 3},
        tags=["field-note"],
    )
    plan = MovementDecision(
        id="plan_1",
        farm_id=farm.id,
        herd_id=herd.id,
        for_date=date.today(),
        action="MOVE",
        reasoning=["Current paddock is short."],
        confidence="medium",
        source_paddock_id=paddock.id,
        target_paddock_id="paddock_2",
        knowledge_entry_ids=["knowledge_1"],
        status="pending",
        farmer_feedback=None,
        created_at=datetime.utcnow(),
    )

    assert store.create_farm(farm) == farm.id
    assert store.upsert_land_unit(paddock) == paddock.id
    assert store.create_herd(herd) == herd.id
    assert store.record_observation(observation) == observation.id
    assert store.create_plan(plan) == plan.id

    loaded_farm = store.get_farm(farm.id)
    assert loaded_farm is not None
    assert loaded_farm.location == farm.location
    assert loaded_farm.herd_ids == [herd.id]

    assert store.get_land_unit(paddock.id) is not None
    assert store.list_land_units(farm.id, unit_type="paddock")[0].id == paddock.id
    assert store.get_herds(farm.id)[0].current_paddock_id == paddock.id
    assert store.get_recent_observations(farm.id, days=7)[0].id == observation.id
    assert store.get_paddock_observations(paddock.id, days=7)[0].id == observation.id
    latest_plan = store.get_latest_plan(farm.id)
    assert latest_plan is not None
    assert latest_plan.id == plan.id

    store.update_plan_status(plan.id, "approved", "Move them this afternoon.")
    store.update_herd_position(herd.id, "paddock_2")

    updated_plan = store.get_plan(plan.id)
    updated_herd = store.get_herds(farm.id)[0]
    assert updated_plan is not None
    assert updated_plan.status == "approved"
    assert updated_plan.farmer_feedback == "Move them this afternoon."
    assert updated_herd.current_paddock_id == "paddock_2"


def test_sqlite_store_round_trips_land_units(tmp_path):
    store = build_store(tmp_path)
    farm = Farm(id="farm_geo", name="Duck River", timezone="America/Chicago")
    pasture_geometry = GeoFeature.from_geojson(
        {
            "type": "Polygon",
            "coordinates": [[[-87.043, 35.646], [-87.038, 35.646], [-87.038, 35.64], [-87.043, 35.64]]],
        }
    )
    pasture = LandUnit(
        id="pasture_west",
        farm_id=farm.id,
        unit_type="pasture",
        name="West Pasture",
        geometry=pasture_geometry,
        confidence=0.55,
        provenance={"source": "map_screenshot"},
        warnings=["Estimated from screenshot."],
    )

    store.create_farm(farm)
    assert store.upsert_land_unit(pasture) == pasture.id

    loaded = store.get_land_unit(pasture.id)
    assert loaded is not None
    assert loaded.geometry.to_geojson()["geometry"]["type"] == "Polygon"
    assert loaded.provenance == {"source": "map_screenshot"}
    assert loaded.warnings == ["Estimated from screenshot."]
    assert store.list_land_units(farm.id, unit_type="pasture")[0].id == pasture.id


def test_sqlite_store_round_trips_multipolygon_farm_boundary(tmp_path):
    store = build_store(tmp_path)
    boundary = GeoFeature.from_geojson(
        {
            "type": "MultiPolygon",
            "coordinates": [
                [[[-87.05, 35.65], [-87.04, 35.65], [-87.04, 35.64], [-87.05, 35.65]]],
                [[[-87.03, 35.63], [-87.02, 35.63], [-87.02, 35.62], [-87.03, 35.63]]],
            ],
        }
    )
    farm = Farm(id="farm_multi", name="Two Parcel Farm", timezone="America/Chicago", boundary=boundary)

    store.create_farm(farm)

    loaded = store.get_farm(farm.id)
    assert loaded is not None
    assert loaded.boundary is not None
    assert loaded.boundary.to_geojson()["geometry"]["type"] == "MultiPolygon"


def test_sqlite_store_round_trips_pipelines_and_farmer_actions(tmp_path):
    store = build_store(tmp_path)
    farm = Farm(
        id="farm_1",
        name="Willow Creek",
        timezone="America/Chicago",
        location=GeoPoint(longitude=-95.2, latitude=36.2),
    )
    pipeline = DataPipeline(
        id="pipeline_1",
        farm_id=farm.id,
        name="nofence",
        profile_id="nofence-farm_1",
        login_url="https://app.nofence.no/login",
        target_urls=["https://app.nofence.no/dashboard"],
        extraction_prompts=["Extract today's GPS positions as observations."],
        observation_source="nofence",
        observation_tags=["gps", "integration"],
        vendor_skill_version="sha256:abc123",
    )
    action = FarmerAction(
        id="action_1",
        farm_id=farm.id,
        action_type="reauth",
        summary="Reconnect NoFence.",
        context={"pipeline_id": pipeline.id},
    )

    store.create_farm(farm)
    assert store.create_pipeline(pipeline) == pipeline.id
    assert store.create_farmer_action(action) == action.id

    loaded_pipeline = store.get_pipeline(pipeline.id)
    assert loaded_pipeline is not None
    assert loaded_pipeline.profile_id == pipeline.profile_id
    assert loaded_pipeline.observation_tags == ["gps", "integration"]
    assert store.list_pipelines(farm.id)[0].id == pipeline.id

    pending_actions = store.list_pending_actions(farm.id)
    assert len(pending_actions) == 1
    assert pending_actions[0].context == {"pipeline_id": pipeline.id}

    collected_at = datetime.utcnow()
    store.update_pipeline(
        pipeline.id,
        enabled=False,
        last_collected_at=collected_at,
        last_error="Session expired",
    )
    store.resolve_farmer_action(action.id, "Farmer reconnected the account.")

    updated_pipeline = store.get_pipeline(pipeline.id)
    assert updated_pipeline is not None
    assert updated_pipeline.enabled is False
    assert updated_pipeline.last_error == "Session expired"
    assert updated_pipeline.last_collected_at == collected_at
    assert store.list_pending_actions(farm.id) == []


def test_sqlite_activity_feed_rolls_up_to_profiles_and_manifest(tmp_path):
    store = build_store(tmp_path)
    farm = Farm(id="farm_activity", name="Cedar Hollow", timezone="America/Chicago")
    pasture = LandUnit(
        id="pasture_1",
        farm_id=farm.id,
        unit_type="pasture",
        name="South Pasture",
        geometry=GeoFeature.from_geojson(
            {
                "type": "Polygon",
                "coordinates": [[[-95.21, 36.21], [-95.22, 36.21], [-95.22, 36.22], [-95.21, 36.21]]],
            }
        ),
    )
    paddock = LandUnit(
        id="paddock_1",
        farm_id=farm.id,
        parent_id=pasture.id,
        unit_type="paddock",
        name="South A",
        geometry=pasture.geometry,
    )
    herd = Herd(id="herd_1", farm_id=farm.id, species="cattle", count=12, current_paddock_id=paddock.id)
    animal = Animal(
        id="animal_1",
        farm_id=farm.id,
        herd_id=herd.id,
        species="cattle",
        sex="female",
        tag="A12",
        breed="Angus",
        current_paddock_id=paddock.id,
    )
    observation = Observation(
        id="obs_activity",
        farm_id=farm.id,
        source="photo",
        observed_at=datetime.utcnow(),
        content="A12 has a small scrape on her left flank.",
        paddock_id=paddock.id,
        herd_id=herd.id,
        media_url="https://example.com/a12.jpg",
        media_thumbnail_url="https://example.com/a12-thumb.jpg",
        media_metadata={"cloud_media_asset_id": "media_123"},
        tags=["health"],
    )

    store.create_farm(farm)
    store.upsert_land_unit(pasture)
    store.upsert_land_unit(paddock)
    store.create_herd(herd)
    store.create_animal(animal)
    store.record_observation(observation)

    pasture_feed = store.list_activity_feed(farm.id, "pasture", pasture.id)
    paddock_feed = store.list_activity_feed(farm.id, "paddock", paddock.id)
    herd_feed = store.list_activity_feed(farm.id, "herd", herd.id)
    animal_feed = store.list_animal_activity(animal.id)

    assert any(event.event_type == "image_observation" for event in pasture_feed)
    image_event = next(event for event in pasture_feed if event.event_type == "image_observation")
    assert image_event.attachments[0].url == "https://example.com/a12.jpg"
    assert image_event.attachments[0].thumbnail_url == "https://example.com/a12-thumb.jpg"
    assert image_event.attachments[0].metadata["cloud_media_asset_id"] == "media_123"
    assert any(event.event_type == "image_observation" for event in paddock_feed)
    assert any(event.event_type == "image_observation" for event in herd_feed)
    assert any(event.event_type == "animal_created" for event in animal_feed)

    manifest = build_profile_manifest(store, farm_id=farm.id, subject_type="pasture", subject_id=pasture.id)
    assert manifest["type"] == "openpasture-profile-manifest"
    assert manifest["activity_digest"]["total"] >= 1
    assert manifest["timeline"]["containers"][0]["activities"]
