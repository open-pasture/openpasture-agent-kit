from __future__ import annotations

import json
from datetime import datetime

from openpasture.domain import Observation
from openpasture.ingestion.weather import WeatherObservationPipeline
from openpasture.plugin import register


class _FakeContext:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}
        self.hooks: dict[str, object] = {}
        self.messages: list[str] = []

    def register_tool(self, name, toolset, schema, handler, **kwargs) -> None:
        del toolset, schema, kwargs
        self.tools[name] = handler

    def register_hook(self, name, handler) -> None:
        self.hooks[name] = handler

    def inject_message(self, content: str, role: str = "user") -> bool:
        self.messages.append(f"{role}:{content}")
        return True


def test_registered_handlers_accept_hermes_kwargs(monkeypatch):
    def fake_collect(self, farm_id: str):
        return [
            Observation(
                id="weather_plugin_obs",
                farm_id=farm_id,
                source="weather",
                observed_at=datetime.utcnow(),
                content="Weather outlook: dry and mild.",
                metrics={"temperature_c": 18},
                tags=["weather"],
            )
        ]

    monkeypatch.setattr(WeatherObservationPipeline, "collect", fake_collect)

    ctx = _FakeContext()
    register(ctx)

    farm_result = json.loads(
        ctx.tools["register_farm"](
            task_id="task_register",
            name="Plugin Farm",
            timezone="America/Chicago",
            location={"longitude": -95.2, "latitude": 36.2},
            herd={"id": "herd_plugin", "species": "cattle", "count": 40},
        )
    )
    farm_id = farm_result["farm"]["id"]

    ctx.tools["add_paddock"](
        task_id="task_paddock_current",
        farm_id=farm_id,
        paddock_id="paddock_current",
        name="Current",
        status="grazing",
        geometry=[
            {"longitude": -95.2, "latitude": 36.2},
            {"longitude": -95.21, "latitude": 36.2},
            {"longitude": -95.21, "latitude": 36.21},
        ],
    )
    ctx.tools["add_paddock"](
        task_id="task_paddock_next",
        farm_id=farm_id,
        paddock_id="paddock_next",
        name="Next",
        status="resting",
        geometry=[
            {"longitude": -95.22, "latitude": 36.2},
            {"longitude": -95.23, "latitude": 36.2},
            {"longitude": -95.23, "latitude": 36.21},
        ],
    )
    ctx.tools["set_herd_position"](
        task_id="task_set_position",
        herd_id="herd_plugin",
        paddock_id="paddock_current",
    )
    ctx.tools["record_observation"](
        task_id="task_observation",
        farm_id=farm_id,
        source="field",
        content="Current paddock is getting short and muddy near the water point.",
        paddock_id="paddock_current",
        herd_id="herd_plugin",
        tags=["field-note"],
    )

    lesson_result = json.loads(
        ctx.tools["store_lesson"](
            task_id="task_store_lesson",
            content="Back fencing protects fresh regrowth from immediate re-bite.",
            entry_type="principle",
            category="grazing-management",
            tags=["back-fencing", "recovery"],
            author="Greg Judy",
            source_url="https://example.com/video-a",
            source_title="Back Fencing Basics",
            source_kind="youtube",
        )
    )
    assert lesson_result["status"] == "ok"

    brief_result = json.loads(
        ctx.tools["generate_morning_brief"](
            task_id="task_brief",
            farm_id=farm_id,
        )
    )
    assert brief_result["brief"]["recommendation"]["action"] == "MOVE"

    search_result = json.loads(
        ctx.tools["search_knowledge"](
            task_id="task_search",
            query="back fencing recovery",
        )
    )
    assert search_result["entries"]
