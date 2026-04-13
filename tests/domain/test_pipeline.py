from __future__ import annotations

from openpasture.domain import DataPipeline, FarmerAction


def test_data_pipeline_defaults_are_pipeline_friendly():
    pipeline = DataPipeline(
        id="pipeline_1",
        farm_id="farm_1",
        name="nofence",
        profile_id="nofence-farm_1",
        login_url="https://app.nofence.no/login",
        target_urls=["https://app.nofence.no/dashboard"],
        extraction_prompts=["Extract today's fence alerts as observations."],
        observation_source="nofence",
    )

    assert pipeline.observation_tags == []
    assert pipeline.schedule == "0 5 * * *"
    assert pipeline.enabled is True
    assert pipeline.last_collected_at is None
    assert pipeline.last_error is None


def test_farmer_action_defaults_to_empty_context():
    action = FarmerAction(
        id="action_1",
        farm_id="farm_1",
        action_type="reauth",
        summary="Reconnect NoFence.",
    )

    assert action.context == {}
    assert action.resolved_at is None
    assert action.resolution is None
