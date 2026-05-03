from __future__ import annotations

import json
from datetime import datetime

import pytest

from openpasture.domain import Observation
from openpasture.ingestion.weather import WeatherObservationPipeline
from openpasture.runtime import get_store, initialize, set_active_farm_id
from openpasture.tools.brief import handle_generate_morning_brief
from openpasture.tools.farm import handle_get_farm_state, handle_register_farm
from openpasture.tools.observe import handle_record_observation
from openpasture.tools.onboarding import handle_setup_initial_farm

pytestmark = pytest.mark.alpha


def test_record_observation_normalizes_field_aliases(monkeypatch):
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

    result = json.loads(
        handle_setup_initial_farm(
            {
                "name": "Alias Farm",
                "timezone": "America/Chicago",
                "herd": {"id": "herd_1", "species": "cattle", "count": 40},
                "paddocks": [
                    {
                        "id": "paddock_current",
                        "name": "Current",
                        "status": "grazing",
                        "geometry": [
                            {"longitude": -95.2, "latitude": 36.2},
                            {"longitude": -95.21, "latitude": 36.2},
                            {"longitude": -95.21, "latitude": 36.21},
                        ],
                    },
                    {
                        "id": "paddock_next",
                        "name": "Next",
                        "status": "resting",
                        "geometry": [
                            {"longitude": -95.22, "latitude": 36.2},
                            {"longitude": -95.23, "latitude": 36.2},
                            {"longitude": -95.23, "latitude": 36.21},
                        ],
                    },
                ],
            }
        )
    )
    farm_id = result["farm"]["id"]

    handle_record_observation(
        {
            "farm_id": farm_id,
            "source": "field_observation",
            "content": "Current paddock is getting short and muddy near the water point.",
            "paddock_id": "paddock_current",
            "herd_id": "herd_1",
        }
    )

    observations = get_store().get_recent_observations(farm_id, days=7)
    assert observations[0].source == "field"

    brief_result = json.loads(handle_generate_morning_brief({"farm_id": farm_id}))
    assert brief_result["brief"]["recommendation"]["action"] == "MOVE"


def test_register_farm_blocks_second_farm_without_explicit_override():
    initialize()

    handle_register_farm({"name": "Primary Farm", "timezone": "America/Chicago"})

    with pytest.raises(ValueError, match="allow_additional_farm"):
        handle_register_farm({"name": "Duplicate Farm", "timezone": "America/Chicago"})

    second_farm = json.loads(
        handle_register_farm(
            {
                "name": "Admin Farm",
                "timezone": "America/Chicago",
                "allow_additional_farm": True,
            }
        )
    )

    assert second_farm["farm"]["name"] == "Admin Farm"


def test_setup_initial_farm_captures_flexible_geo_context_and_initial_position():
    initialize()

    result = json.loads(
        handle_setup_initial_farm(
            {
                "name": "Onboarding Farm",
                "timezone": "America/Chicago",
                "location_hint": "Google Maps screenshot near the creek bend south of County Road 12.",
                "boundary_hint": "Rough rectangle from the barn to the road and back along the creek.",
                "herd": {"id": "herd_alpha", "species": "cattle", "count": 25},
                "paddocks": [
                    {
                        "id": "paddock_home",
                        "name": "Home",
                        "status": "grazing",
                        "boundary_hint": "Triangle behind the barn and north fence.",
                    },
                    {
                        "id": "paddock_north",
                        "name": "North",
                        "status": "resting",
                    },
                ],
            }
        )
    )

    assert result["workflow"] == "onboarding"
    assert result["onboarding_status"]["farm_ready"] is True
    assert result["onboarding_status"]["herd_ready"] is True
    assert result["onboarding_status"]["paddocks_ready"] is True
    assert result["herds"][0]["current_paddock_id"] == "paddock_home"
    assert "Onboarding location context" in result["farm"]["notes"]
    assert "Onboarding boundary context" in result["farm"]["notes"]
    assert "Onboarding paddock boundary context" in result["paddocks"][0]["notes"]


def test_setup_initial_farm_preserves_chatgpt_extracted_maps_location():
    initialize()

    result = json.loads(
        handle_setup_initial_farm(
            {
                "name": "Maps Pin Farm",
                "timezone": "America/Chicago",
                "location": {"type": "Point", "coordinates": [-95.2345, 36.4567]},
                "location_hint": "Google Maps screenshot showed a dropped pin at 36.4567, -95.2345.",
                "herd": {"id": "herd_maps", "species": "cattle", "count": 18},
                "paddocks": [{"id": "paddock_home", "name": "Home", "status": "grazing"}],
            }
        )
    )

    assert result["farm"]["location"] == {"type": "Point", "coordinates": [-95.2345, 36.4567]}
    assert "Google Maps screenshot" in result["farm"]["notes"]
    assert result["herds"][0]["current_paddock_id"] == "paddock_home"


def test_setup_initial_farm_refines_existing_farm_without_duplicate_herds():
    initialize()

    first = json.loads(
        handle_setup_initial_farm(
            {
                "name": "Elm Spring",
                "timezone": "America/Chicago",
                "location": {"type": "Point", "coordinates": [-95.1, 36.1]},
                "herd": {"id": "herd_existing", "species": "cattle", "count": 18},
                "paddocks": [{"id": "paddock_home", "name": "Home", "status": "grazing"}],
            }
        )
    )

    refined = json.loads(
        handle_setup_initial_farm(
            {
                "name": "Duck River Farm",
                "timezone": "America/Chicago",
                "location": {"longitude": -95.2345, "latitude": 36.4567},
                "herd": {"id": "herd_new", "species": "cattle", "count": 20},
                "paddocks": [{"id": "paddock_home", "name": "Home", "status": "grazing"}],
                "current_paddock_id": "paddock_home",
            }
        )
    )

    assert refined["farm"]["id"] == first["farm"]["id"]
    assert refined["farm"]["name"] == "Duck River Farm"
    assert refined["farm"]["location"] == {"type": "Point", "coordinates": [-95.2345, 36.4567]}
    assert [herd["id"] for herd in refined["herds"]] == ["herd_existing"]
    assert refined["herds"][0]["current_paddock_id"] == "paddock_home"


def test_setup_initial_farm_preserves_existing_location_when_only_hint_is_passed():
    initialize()

    first = json.loads(
        handle_setup_initial_farm(
            {
                "name": "Elm Spring",
                "timezone": "America/Chicago",
                "location": {"type": "Point", "coordinates": [-95.1, 36.1]},
                "herd": {"id": "herd_existing", "species": "cattle", "count": 18},
                "paddocks": [{"id": "paddock_home", "name": "Home", "status": "grazing"}],
            }
        )
    )

    refined = json.loads(
        handle_setup_initial_farm(
            {
                "name": "Elm Spring Pastures",
                "timezone": "America/Chicago",
                "location_hint": "Screenshot shows a marker near the old barn, but no visible coordinates.",
                "herd": {"id": "herd_existing", "species": "cattle", "count": 18},
                "paddocks": [{"id": "paddock_home", "name": "Home", "status": "grazing"}],
            }
        )
    )

    assert refined["farm"]["id"] == first["farm"]["id"]
    assert refined["farm"]["name"] == "Elm Spring Pastures"
    assert refined["farm"]["location"] == {"type": "Point", "coordinates": [-95.1, 36.1]}
    assert "no visible coordinates" in refined["farm"]["notes"]
    assert len(refined["herds"]) == 1


def test_setup_initial_farm_accepts_top_level_herd_aliases_and_loose_count():
    initialize()

    result = json.loads(
        handle_setup_initial_farm(
            {
                "name": "Alias Herd Farm",
                "timezone": "America/Chicago",
                "herd_id": "herd_alias",
                "herd_species": "cattle",
                "herd_count": "28 head",
                "current_paddock_name": "Home",
                "paddocks": [
                    {
                        "id": "paddock_home",
                        "name": "Home",
                        "status": "grazing",
                    }
                ],
            }
        )
    )

    assert result["herds"][0]["id"] == "herd_alias"
    assert result["herds"][0]["species"] == "cattle"
    assert result["herds"][0]["count"] == 28
    assert result["herds"][0]["current_paddock_id"] == "paddock_home"


def test_setup_initial_farm_missing_payload_error_includes_example():
    initialize()

    with pytest.raises(ValueError, match="Do not call it with empty args"):
        handle_setup_initial_farm({})


def test_daily_tools_fall_back_to_single_farm_context_and_aliases(monkeypatch):
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

    result = json.loads(
        handle_setup_initial_farm(
            {
                "name": "Fallback Farm",
                "timezone": "America/Chicago",
                "herd": {"id": "herd_1", "species": "cattle", "count": 40},
                "paddocks": [
                    {
                        "id": "paddock_current",
                        "name": "Current",
                        "status": "grazing",
                    },
                    {
                        "id": "paddock_next",
                        "name": "Next",
                        "status": "resting",
                    },
                ],
            }
        )
    )
    farm_id = result["farm"]["id"]
    set_active_farm_id(None)

    handle_record_observation(
        {
            "type": "field",
            "text": "Current paddock is getting short and muddy near the water point.",
            "paddock_id": "paddock_current",
            "herd_id": "herd_1",
        }
    )

    observations = get_store().get_recent_observations(farm_id, days=7)
    assert any(observation.source == "field" for observation in observations)

    state = json.loads(handle_get_farm_state({}))
    assert state["farm"]["id"] == farm_id

    brief_result = json.loads(handle_generate_morning_brief({}))
    assert brief_result["brief"]["recommendation"]["action"] == "MOVE"


def test_missing_farm_id_stays_ambiguous_with_multiple_farms():
    initialize()

    handle_register_farm({"name": "Primary Farm", "timezone": "America/Chicago"})
    handle_register_farm(
        {
            "name": "Second Farm",
            "timezone": "America/Chicago",
            "allow_additional_farm": True,
        }
    )
    set_active_farm_id(None)

    with pytest.raises(ValueError, match="Multiple farms"):
        handle_get_farm_state({})

    with pytest.raises(ValueError, match="Multiple farms"):
        handle_generate_morning_brief({})

    with pytest.raises(ValueError, match="Multiple farms"):
        handle_record_observation({"source": "field", "content": "Forage is short."})
