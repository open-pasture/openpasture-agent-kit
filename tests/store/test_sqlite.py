from __future__ import annotations

from datetime import date, datetime

from openpasture.domain import (
    DataPipeline,
    Farm,
    FarmerAction,
    GeoPoint,
    GeoPolygon,
    Herd,
    MovementDecision,
    Observation,
    Paddock,
)
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
    paddock = Paddock(
        id="paddock_1",
        farm_id=farm.id,
        name="North 40",
        geometry=GeoPolygon(
            coordinates=[
                GeoPoint(-95.21, 36.21),
                GeoPoint(-95.22, 36.21),
                GeoPoint(-95.22, 36.22),
            ]
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
    assert store.create_paddock(paddock) == paddock.id
    assert store.create_herd(herd) == herd.id
    assert store.record_observation(observation) == observation.id
    assert store.create_plan(plan) == plan.id

    loaded_farm = store.get_farm(farm.id)
    assert loaded_farm is not None
    assert loaded_farm.location == farm.location
    assert loaded_farm.paddock_ids == [paddock.id]
    assert loaded_farm.herd_ids == [herd.id]

    assert store.get_paddock(paddock.id) is not None
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
