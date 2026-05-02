from __future__ import annotations

import json
from pathlib import Path

import pytest

from openpasture.runtime import initialize, reset_runtime
from openpasture.tools.geo import handle_get_farm_geo_state, handle_save_geo_onboarding_draft

FIXTURE_IMAGE = Path(
    "/Users/codymenefee/.cursor/projects/Users-codymenefee-Documents-openPasture/assets/"
    "Screenshot_2026-04-30_at_10.54.52_PM-0cda64e2-7227-43a7-aede-791b8f6aed80.png"
)


@pytest.fixture(autouse=True)
def runtime(tmp_path, monkeypatch):
    reset_runtime()
    monkeypatch.setenv("OPENPASTURE_CLOUD_BASE_URL", "https://cloud.openpasture.test")
    initialize({"data_dir": tmp_path / ".openpasture"})
    yield
    reset_runtime()


def test_save_geo_onboarding_draft_from_google_maps_fixture_facts():
    if not FIXTURE_IMAGE.exists():
        pytest.skip("Google Maps screenshot fixture is only available in the Cursor workspace.")

    result = json.loads(
        handle_save_geo_onboarding_draft(
            {
                "name": "Duck River Screenshot Farm",
                "timezone": "America/Chicago",
                "location": {"type": "Point", "coordinates": [-87.038675, 35.642109]},
                "boundary": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-87.0432, 35.6466],
                            [-87.0334, 35.6466],
                            [-87.0334, 35.6389],
                            [-87.0432, 35.6389],
                            [-87.0432, 35.6466],
                        ]
                    ],
                },
                "source": "map_screenshot",
                "confidence": 0.55,
                "evidence": [str(FIXTURE_IMAGE), "Visible pin reads 35.642109, -87.038675."],
                "pastures": [
                    {
                        "id": "pasture_west_box",
                        "name": "West boxed pasture",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-87.0426, 35.6462],
                                    [-87.0385, 35.6462],
                                    [-87.0385, 35.6397],
                                    [-87.0426, 35.6397],
                                    [-87.0426, 35.6462],
                                ]
                            ],
                        },
                        "warnings": ["Estimated from the left red screenshot box."],
                    },
                    {
                        "id": "pasture_east_box",
                        "name": "East boxed pasture",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-87.0386, 35.6440],
                                    [-87.0341, 35.6440],
                                    [-87.0341, 35.6398],
                                    [-87.0386, 35.6398],
                                    [-87.0386, 35.6440],
                                ]
                            ],
                        },
                        "warnings": ["Estimated from the right red screenshot box."],
                    },
                ],
            }
        )
    )

    assert result["status"] == "ok"
    assert result["map_url"] == f"https://cloud.openpasture.test/dashboard/farm/map?farmId={result['farm']['id']}&edit=1"
    assert len(result["land_units"]) == 2
    assert all(unit["provenance"]["source"] == "map_screenshot" for unit in result["land_units"])
    assert all(unit["confidence"] < 1 for unit in result["land_units"])

    geo_state = json.loads(handle_get_farm_geo_state({"farm_id": result["farm"]["id"]}))
    assert geo_state["farm"]["location"]["coordinates"] == [-87.038675, 35.642109]
    assert {unit["id"] for unit in geo_state["land_units"]} == {"pasture_west_box", "pasture_east_box"}
