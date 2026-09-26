from __future__ import annotations

from datetime import datetime, timedelta, timezone

from openpasture import calculations
from openpasture.domain import CueEvent, PositionFix

NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)


def test_grazing_pressure_splits_herd_time_by_fix_share():
    pressure = calculations.grazing_pressure(
        {"p1": 30, "p2": 10}, herd_count=40, window_days=1.0, area_hectares={"p1": 4.0, "p2": None}
    )

    assert pressure["p1"]["share_of_time"] == 0.75
    assert pressure["p1"]["animal_days"] == 30.0
    assert pressure["p1"]["animal_days_per_acre"] == round(30 / (4 * calculations.ACRES_PER_HECTARE), 2)
    assert pressure["p2"]["animal_days_per_acre"] is None
    assert calculations.grazing_pressure({}, herd_count=40, window_days=1, area_hectares={}) == {}


def test_rest_days_and_unknowns():
    rest = calculations.rest_days({"p1": NOW - timedelta(days=38), "p2": None, "p3": NOW}, NOW)

    assert rest == {"p1": 38.0, "p2": None, "p3": 0.0}


def test_forage_prefers_farmer_height_over_imagery():
    farmer = calculations.forage_estimate(ndvi_mean=0.8, height_inches=5)
    imagery = calculations.forage_estimate(ndvi_mean=0.62)

    assert farmer["source"] == "farmer" and farmer["height_inches"] == 5.0
    assert farmer["available_kg_dm_per_ha"] == round(2 * calculations.KG_DM_PER_HA_PER_INCH)
    assert imagery["source"] == "imagery" and imagery["confidence"] == "low"
    assert imagery["height_inches"] == 7.0
    assert calculations.forage_estimate()["source"] is None


def test_recovery_trend_labels_slope():
    rising = calculations.recovery_trend([(NOW - timedelta(days=14), 0.40), (NOW - timedelta(days=7), 0.48), (NOW, 0.56)])
    falling = calculations.recovery_trend([(NOW - timedelta(days=7), 0.6), (NOW, 0.5)])

    assert rising["trend"] == "recovering"
    assert falling["trend"] == "declining"
    assert calculations.recovery_trend([(NOW, 0.5)])["trend"] == "unknown"


def test_feed_budget_days():
    days = calculations.feed_budget_days(available_kg_dm=10_000, herd_animal_units=20)

    assert days == round(10_000 * 0.6 / (20 * calculations.DEFAULT_INTAKE_KG_DM_PER_AU_DAY), 1)
    assert calculations.feed_budget_days(available_kg_dm=100, herd_animal_units=1, daily_growth_kg_dm=50) == 365.0
    assert calculations.feed_budget_days(available_kg_dm=100, herd_animal_units=0) is None


def test_risk_flags_from_land_report_sections():
    sections = {
        "weather": {
            "forecast": [
                {"date": "2026-09-26", "precip_mm": 30.0, "temp_max_c": 36.0, "temp_min_c": 20.0},
                {"date": "2026-09-27", "precip_mm": 25.0, "temp_max_c": 30.0, "temp_min_c": 18.0},
            ],
            "history": [{"date": "2026-09-24", "precip_mm": 26.0}],
        },
        "water": {"floodplain": {"in_floodplain": True}},
        "climate": {"drought": {"category": "D2"}},
        "soil": None,
    }
    flags = {flag["type"]: flag for flag in calculations.risk_flags(sections)}

    assert flags["heat"]["level"] == "high"
    assert flags["flood"]["level"] == "high"
    assert "floodplain" in flags["flood"]["reason"]
    assert flags["wet_ground"]["level"] == "medium"
    assert flags["drought"]["level"] == "high"
    assert calculations.risk_flags({"weather": None}) == []


def test_behavior_shares_and_cues():
    fixes = [
        PositionFix("c1", NOW, [0, 0], activity="grazing"),
        PositionFix("c1", NOW, [0, 0], activity="grazing"),
        PositionFix("c2", NOW, [0, 0], activity="resting"),
        PositionFix("c2", NOW, [0, 0]),
    ]
    cues = [CueEvent("c1", NOW, margin_meters=-1.4), CueEvent("c2", NOW, margin_meters=2.0)]
    result = calculations.behavior(fixes, cues, window_days=1.0)

    assert result["grazing_share"] == round(2 / 3, 3)
    assert result["resting_share"] == round(1 / 3, 3)
    assert result["cue_count"] == 2
    assert result["cues_per_collar_day"] == 1.0
    assert result["cues_past_line"] == 1


def test_animal_units():
    assert calculations.animal_units("cattle", 28) == 28.0
    assert calculations.animal_units("sheep", 100) == 20.0
    assert calculations.animal_units("cattle", 28, 30.5) == 30.5
