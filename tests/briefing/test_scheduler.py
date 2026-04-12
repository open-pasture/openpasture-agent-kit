from __future__ import annotations

import json
from datetime import datetime

from openpasture.ingestion.weather import WeatherObservationPipeline
from openpasture.runtime import get_brief_scheduler, get_store, initialize
from openpasture.tools.farm import handle_add_paddock, handle_register_farm, handle_set_herd_position
from openpasture.tools.observe import handle_record_observation


def test_register_farm_schedules_daily_brief(monkeypatch):
    initialize()

    farm_result = json.loads(
        handle_register_farm(
            {
                "name": "Scheduled Farm",
                "timezone": "America/Chicago",
                "location": {"longitude": -95.2, "latitude": 36.2},
                "herd": {
                    "id": "herd_scheduled",
                    "species": "cattle",
                    "count": 40,
                },
            }
        )
    )
    farm_id = farm_result["farm"]["id"]

    scheduler = get_brief_scheduler()
    job = scheduler._scheduler.get_job(f"morning-brief:{farm_id}")
    assert job is not None


def test_scheduler_run_persists_and_delivers_brief(monkeypatch):
    delivered_messages: list[str] = []

    def deliver(message: str) -> bool:
        delivered_messages.append(message)
        return True

    def fake_collect(self, farm_id: str):
        from openpasture.domain import Observation

        return [
            Observation(
                id="weather_scheduler_obs",
                farm_id=farm_id,
                source="weather",
                observed_at=datetime.utcnow(),
                content="Weather outlook: dry and mild.",
                metrics={"temperature_c": 18},
                tags=["weather"],
            )
        ]

    monkeypatch.setattr(WeatherObservationPipeline, "collect", fake_collect)

    initialize(delivery_handler=deliver)

    register_result = json.loads(
        handle_register_farm(
            {
                "name": "Scheduler Flow Farm",
                "timezone": "America/Chicago",
                "location": {"longitude": -95.2, "latitude": 36.2},
                "herd": {
                    "id": "herd_scheduler",
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
    handle_set_herd_position({"herd_id": "herd_scheduler", "paddock_id": "paddock_current"})
    handle_record_observation(
        {
            "farm_id": farm_id,
            "source": "field",
            "content": "Current paddock is getting short and muddy near the water point.",
            "paddock_id": "paddock_current",
            "herd_id": "herd_scheduler",
            "tags": ["field-note"],
        }
    )

    brief = get_brief_scheduler().run_brief_now(farm_id)

    assert brief.recommendation.action == "MOVE"
    assert delivered_messages
    assert "Scheduled morning brief" in delivered_messages[0]

    store = get_store()
    saved_brief = store.get_daily_brief(brief.id)
    assert saved_brief is not None
