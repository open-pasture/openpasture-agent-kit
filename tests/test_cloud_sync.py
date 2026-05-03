from __future__ import annotations

from openpasture.connectors.cloud_sync import build_farm_geo_sync_batches


def test_build_farm_geo_sync_batches_includes_land_units():
    batches = build_farm_geo_sync_batches(
        {
            "farm": {
                "id": "farm_1",
                "name": "Willow Creek",
                "timezone": "America/Chicago",
            },
            "land_units": [
                {
                    "id": "pasture_north",
                    "farm_id": "farm_1",
                    "unit_type": "pasture",
                    "name": "North Pasture",
                    "geometry": {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-95.2, 36.2],
                                    [-95.1, 36.2],
                                    [-95.1, 36.3],
                                    [-95.2, 36.3],
                                    [-95.2, 36.2],
                                ]
                            ],
                        },
                    },
                    "area_hectares": 12.5,
                    "confidence": 0.82,
                    "provenance": {"source": "dashboard_draw"},
                    "geometry_version": 3,
                    "status": "draft",
                    "notes": "Farmer adjusted in portal.",
                    "warnings": ["Needs field check."],
                }
            ],
        },
        synced_at=1234,
    )

    assert [batch["table"] for batch in batches] == ["farms", "landUnits"]
    land_unit = batches[1]["records"][0]
    assert land_unit == {
        "agentFarmId": "farm_1",
        "agentLandUnitId": "pasture_north",
        "unitType": "pasture",
        "name": "North Pasture",
        "geometry": {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-95.2, 36.2],
                        [-95.1, 36.2],
                        [-95.1, 36.3],
                        [-95.2, 36.3],
                        [-95.2, 36.2],
                    ]
                ],
            },
        },
        "areaHectares": 12.5,
        "confidence": 0.82,
        "provenance": {"source": "dashboard_draw"},
        "geometryVersion": 3,
        "status": "draft",
        "notes": "Farmer adjusted in portal.",
        "warnings": ["Needs field check."],
        "syncedAt": 1234,
    }


def test_build_farm_geo_sync_batches_skips_unsupported_land_unit_types():
    batches = build_farm_geo_sync_batches(
        {
            "farm": {"id": "farm_1", "name": "Willow Creek", "timezone": "UTC"},
            "land_units": [
                {
                    "id": "farm_shell",
                    "unit_type": "farm",
                    "geometry": {"type": "Polygon", "coordinates": []},
                }
            ],
        },
        synced_at=1234,
    )

    assert [batch["table"] for batch in batches] == ["farms"]
