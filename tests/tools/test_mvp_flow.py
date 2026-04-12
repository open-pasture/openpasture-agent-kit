from __future__ import annotations

import json
from datetime import datetime

from openpasture.domain import Observation
from openpasture.ingestion.weather import WeatherObservationPipeline
from openpasture.runtime import initialize
from openpasture.tools.brief import handle_generate_morning_brief
from openpasture.tools.farm import (
    handle_add_paddock,
    handle_get_farm_state,
    handle_register_farm,
    handle_set_herd_position,
)
from openpasture.tools.observe import handle_record_observation
from openpasture.tools.plan import handle_approve_plan


def test_field_ready_flow_moves_herd_using_public_tools(monkeypatch):
    initialize()

    def fake_collect(self, farm_id: str):
        return [
            Observation(
                id="weather_test_obs",
                farm_id=farm_id,
                source="weather",
                observed_at=datetime.utcnow(),
                content="Weather outlook: dry and mild.",
                metrics={"temperature_c": 18},
                tags=["weather"],
            )
        ]

    monkeypatch.setattr(WeatherObservationPipeline, "collect", fake_collect)

    register_result = json.loads(
        handle_register_farm(
            {
                "name": "Field Test Farm",
                "timezone": "America/Chicago",
                "location": {"longitude": -95.2, "latitude": 36.2},
                "herd": {
                    "id": "herd_1",
                    "species": "cattle",
                    "count": 40,
                },
            }
        )
    )
    farm_id = register_result["farm"]["id"]

    handle_add_paddock(
        {
            "farm_id": farm_id,
            "paddock_id": "paddock_current",
            "name": "Current",
            "status": "grazing",
            "geometry": [
                {"longitude": -95.2, "latitude": 36.2},
                {"longitude": -95.21, "latitude": 36.2},
                {"longitude": -95.21, "latitude": 36.21},
            ],
        }
    )
    handle_add_paddock(
        {
            "farm_id": farm_id,
            "paddock_id": "paddock_next",
            "name": "Next",
            "status": "resting",
            "geometry": [
                {"longitude": -95.22, "latitude": 36.2},
                {"longitude": -95.23, "latitude": 36.2},
                {"longitude": -95.23, "latitude": 36.21},
            ],
        }
    )
    handle_set_herd_position(
        {
            "herd_id": "herd_1",
            "paddock_id": "paddock_current",
        }
    )

    handle_record_observation(
        {
            "farm_id": farm_id,
            "source": "manual",
            "content": "Current paddock is getting short and muddy near the water point.",
            "paddock_id": "paddock_current",
            "herd_id": "herd_1",
            "tags": ["field-note"],
        }
    )

    brief_result = json.loads(handle_generate_morning_brief({"farm_id": farm_id}))
    plan = brief_result["brief"]["recommendation"]

    assert plan["action"] == "MOVE"
    assert plan["target_paddock_id"] == "paddock_next"

    approval_result = json.loads(
        handle_approve_plan(
            {
                "plan_id": plan["id"],
                "status": "approved",
            }
        )
    )

    assert approval_result["plan"]["status"] == "approved"

    farm_state = json.loads(handle_get_farm_state({"farm_id": farm_id}))
    herd = farm_state["herds"][0]
    assert herd["current_paddock_id"] == "paddock_next"


def test_observation_with_herd_and_paddock_infers_current_position(monkeypatch):
    initialize()

    def fake_collect(self, farm_id: str):
        return [
            Observation(
                id="weather_test_obs",
                farm_id=farm_id,
                source="weather",
                observed_at=datetime.utcnow(),
                content="Weather outlook: dry and mild.",
                metrics={"temperature_c": 18},
                tags=["weather"],
            )
        ]

    monkeypatch.setattr(WeatherObservationPipeline, "collect", fake_collect)

    register_result = json.loads(
        handle_register_farm(
            {
                "name": "Inference Farm",
                "timezone": "America/Chicago",
                "location": {"longitude": -95.2, "latitude": 36.2},
                "herd": {
                    "id": "herd_1",
                    "species": "cattle",
                    "count": 40,
                },
            }
        )
    )
    farm_id = register_result["farm"]["id"]

    handle_add_paddock(
        {
            "farm_id": farm_id,
            "paddock_id": "paddock_current",
            "name": "Current",
            "status": "grazing",
            "geometry": [
                {"longitude": -95.2, "latitude": 36.2},
                {"longitude": -95.21, "latitude": 36.2},
                {"longitude": -95.21, "latitude": 36.21},
            ],
        }
    )
    handle_add_paddock(
        {
            "farm_id": farm_id,
            "paddock_id": "paddock_next",
            "name": "Next",
            "status": "resting",
            "geometry": [
                {"longitude": -95.22, "latitude": 36.2},
                {"longitude": -95.23, "latitude": 36.2},
                {"longitude": -95.23, "latitude": 36.21},
            ],
        }
    )

    handle_record_observation(
        {
            "farm_id": farm_id,
            "source": "manual",
            "content": "Current paddock is getting short and muddy near the water point.",
            "paddock_id": "paddock_current",
            "herd_id": "herd_1",
            "tags": ["field-note"],
        }
    )

    farm_state = json.loads(handle_get_farm_state({"farm_id": farm_id}))
    assert farm_state["herds"][0]["current_paddock_id"] == "paddock_current"

    brief_result = json.loads(handle_generate_morning_brief({"farm_id": farm_id}))
    plan = brief_result["brief"]["recommendation"]

    assert plan["action"] == "MOVE"
    assert plan["source_paddock_id"] == "paddock_current"
    assert plan["target_paddock_id"] == "paddock_next"
