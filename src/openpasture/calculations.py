"""Grazing calculations: pure functions that turn land and collar data into signals.

Every function here is deliberately simple. The numbers are rules of thumb for
a first read, not measurements, and each docstring says what it assumes so the
agent (and the farmer) can weigh them honestly.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime

from openpasture.domain import CueEvent, PositionFix
from openpasture.domain.clock import as_utc

ACRES_PER_HECTARE = 2.47105
# About 300 lb of dry matter per acre per inch of height in a reasonably dense
# stand, which is ~336 kg/ha per inch. Thin or stemmy stands run lower.
KG_DM_PER_HA_PER_INCH = 336.0
# A 1,000 lb animal unit eats about 2.6% of body weight per day: ~26 lb, ~11.8 kg.
DEFAULT_INTAKE_KG_DM_PER_AU_DAY = 11.8
DEFAULT_RESIDUAL_INCHES = 3.0
DEFAULT_UTILIZATION = 0.6

ANIMAL_UNITS_PER_HEAD = {
    "cattle": 1.0,
    "cow": 1.0,
    "beef": 1.0,
    "dairy": 1.4,
    "bison": 1.0,
    "horse": 1.25,
    "horses": 1.25,
    "sheep": 0.2,
    "goat": 0.15,
    "goats": 0.15,
}


def animal_units(species: str, count: int, stated_animal_units: float | None = None) -> float:
    """Herd size in animal units. Uses the farmer's number when given."""

    if stated_animal_units is not None:
        return float(stated_animal_units)
    return round(ANIMAL_UNITS_PER_HEAD.get(species.strip().lower(), 1.0) * max(count, 0), 2)


def grazing_pressure(
    land_unit_fix_counts: Mapping[str, int],
    *,
    herd_count: int,
    window_days: float,
    area_hectares: Mapping[str, float | None],
) -> dict[str, dict[str, float | None]]:
    """Animal-days and animal-days per acre for each land unit, from collar fixes.

    Assumes the collared animals move like the rest of the herd and that fixes
    are spread evenly in time, so a land unit's share of fixes is its share of
    the herd's time in the window.
    """

    total = sum(count for count in land_unit_fix_counts.values() if count > 0)
    result: dict[str, dict[str, float | None]] = {}
    if total == 0:
        return result
    for land_unit_id, count in land_unit_fix_counts.items():
        share = count / total
        days = herd_count * window_days * share
        hectares = area_hectares.get(land_unit_id)
        acres = hectares * ACRES_PER_HECTARE if hectares else None
        result[land_unit_id] = {
            "share_of_time": round(share, 4),
            "animal_days": round(days, 2),
            "animal_days_per_acre": round(days / acres, 2) if acres else None,
        }
    return result


def rest_days(last_grazed_at: Mapping[str, datetime | None], as_of: datetime) -> dict[str, float | None]:
    """Days since each land unit was last grazed. None when there is no record.

    "Last grazed" is whatever the caller knows: the end of the last decision
    that had the herd there, or the last collar fix inside it. A unit the herd
    is in right now has zero rest.
    """

    result: dict[str, float | None] = {}
    for land_unit_id, grazed_at in last_grazed_at.items():
        if grazed_at is None:
            result[land_unit_id] = None
            continue
        delta = as_utc(as_of) - as_utc(grazed_at)
        result[land_unit_id] = round(max(delta.total_seconds(), 0.0) / 86_400, 1)
    return result


def forage_estimate(
    *,
    ndvi_mean: float | None = None,
    height_inches: float | None = None,
    residual_target_inches: float = DEFAULT_RESIDUAL_INCHES,
) -> dict[str, object]:
    """Standing forage above the residual target, in kg of dry matter per hectare.

    A farmer's measured height wins when present. Otherwise NDVI stands in: it
    is mapped linearly from 0.2 (bare) to 0.8 (about 10 inches). NDVI saturates
    in thick pasture and says nothing about quality or species, so an
    imagery-only estimate is always low confidence.
    """

    source = None
    if height_inches is not None:
        height = float(height_inches)
        source = "farmer"
        confidence = "medium"
    elif ndvi_mean is not None:
        height = max(0.0, (float(ndvi_mean) - 0.2) / 0.6 * 10.0)
        source = "imagery"
        confidence = "low"
    else:
        return {"height_inches": None, "available_kg_dm_per_ha": None, "source": None, "confidence": None}
    available = max(0.0, height - residual_target_inches) * KG_DM_PER_HA_PER_INCH
    return {
        "height_inches": round(height, 1),
        "available_kg_dm_per_ha": round(available),
        "residual_target_inches": residual_target_inches,
        "source": source,
        "confidence": confidence,
    }


def recovery_trend(ndvi_history: Iterable[tuple[datetime, float]]) -> dict[str, object]:
    """NDVI slope per week by least squares, labeled recovering, flat, or declining.

    Needs at least two readings. Cloud contamination and seasonal green-up both
    move NDVI, so treat the label as a prompt to look, not a verdict.
    """

    points = sorted(((as_utc(at), float(value)) for at, value in ndvi_history), key=lambda item: item[0])
    if len(points) < 2:
        return {"trend": "unknown", "ndvi_slope_per_week": None, "readings": len(points)}
    origin = points[0][0]
    xs = [(at - origin).total_seconds() / 604_800 for at, _ in points]
    ys = [value for _, value in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return {"trend": "unknown", "ndvi_slope_per_week": None, "readings": len(points)}
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / denominator
    trend = "recovering" if slope > 0.01 else "declining" if slope < -0.01 else "flat"
    return {"trend": trend, "ndvi_slope_per_week": round(slope, 4), "readings": len(points)}


def feed_budget_days(
    *,
    available_kg_dm: float,
    herd_animal_units: float,
    intake_kg_per_au_day: float = DEFAULT_INTAKE_KG_DM_PER_AU_DAY,
    utilization: float = DEFAULT_UTILIZATION,
    daily_growth_kg_dm: float = 0.0,
) -> float | None:
    """Days of grazing the forage supports for this herd.

    Only ``utilization`` of standing forage is counted as eaten (the rest is
    trampled, fouled, or left as residual). Daily regrowth offsets demand.
    Returns None when the herd has no demand, and caps at 365 days when growth
    outpaces the herd.
    """

    demand = herd_animal_units * intake_kg_per_au_day
    if demand <= 0:
        return None
    net_demand = demand - max(daily_growth_kg_dm, 0.0)
    if net_demand <= 0:
        return 365.0
    return round(min(max(available_kg_dm, 0.0) * utilization / net_demand, 365.0), 1)


def _days(section: Mapping[str, object] | None, key: str) -> list[Mapping[str, object]]:
    if not section:
        return []
    rows = section.get(key)
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _number(row: Mapping[str, object], key: str) -> float | None:
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def risk_flags(sections: Mapping[str, Mapping[str, object] | None]) -> list[dict[str, str]]:
    """Heat, cold, flood, wet-ground, and drought flags from a land report.

    ``sections`` maps section name to its data (``None`` when unavailable).
    Thresholds are for cattle on pasture and are intentionally conservative:
    heat at 32C (35C high), hard cold at -12C, cold rain at or below 0C with
    5 mm or more, flood at 25 mm in a day or 50 mm over three days, wet ground
    after 25 mm in the last three days, drought from the climate section's
    category or from under 15 mm of rain against 60 mm of evapotranspiration
    over the last 30 days.
    """

    flags: list[dict[str, str]] = []
    weather = sections.get("weather")
    forecast = _days(weather, "forecast")[:3]
    history = _days(weather, "history")

    highs = [value for row in forecast if (value := _number(row, "temp_max_c")) is not None]
    lows = [value for row in forecast if (value := _number(row, "temp_min_c")) is not None]
    rain = [_number(row, "precip_mm") or 0.0 for row in forecast]
    if highs and max(highs) >= 32:
        flags.append(
            {
                "type": "heat",
                "level": "high" if max(highs) >= 35 else "medium",
                "reason": f"Highs up to {max(highs):.0f}C in the next 3 days. Shade and water matter.",
            }
        )
    if lows and min(lows) <= -12:
        flags.append({"type": "cold", "level": "high", "reason": f"Lows down to {min(lows):.0f}C in the next 3 days."})
    elif lows and min(lows) <= 0 and sum(rain) >= 5:
        flags.append({"type": "cold", "level": "medium", "reason": "Cold rain in the forecast. Watch for wind exposure."})

    water = sections.get("water") or {}
    floodplain = water.get("floodplain") if isinstance(water, Mapping) else None
    in_floodplain = bool(floodplain.get("in_floodplain")) if isinstance(floodplain, Mapping) else False
    if sum(rain) >= 50 or (rain and max(rain) >= 25):
        level = "high" if sum(rain) >= 50 or in_floodplain else "medium"
        flags.append(
            {
                "type": "flood",
                "level": level,
                "reason": f"{sum(rain):.0f} mm of rain forecast over 3 days"
                + (" on ground in a floodplain." if in_floodplain else "."),
            }
        )

    recent_rain = sum(_number(row, "precip_mm") or 0.0 for row in history[-3:])
    if recent_rain >= 25:
        flags.append(
            {
                "type": "wet_ground",
                "level": "medium",
                "reason": f"{recent_rain:.0f} mm fell in the last 3 days. Low ground may pug.",
            }
        )

    climate = sections.get("climate") or {}
    drought = climate.get("drought") if isinstance(climate, Mapping) else None
    category = str(drought.get("category") or "").lower() if isinstance(drought, Mapping) else ""
    if category in {"d2", "d3", "d4", "severe", "extreme", "exceptional"}:
        flags.append({"type": "drought", "level": "high", "reason": f"Drought category {category.upper()}."})
    elif category in {"d1", "moderate"}:
        flags.append({"type": "drought", "level": "medium", "reason": f"Drought category {category.upper()}."})
    elif len(history) >= 20:
        month = history[-30:]
        precip = sum(_number(row, "precip_mm") or 0.0 for row in month)
        et0 = sum(_number(row, "et0_mm") or 0.0 for row in month)
        if precip < 15 and et0 > 60:
            flags.append(
                {
                    "type": "drought",
                    "level": "medium",
                    "reason": f"Only {precip:.0f} mm of rain against {et0:.0f} mm of evapotranspiration this month.",
                }
            )
    return flags


def behavior(fixes: list[PositionFix], cues: list[CueEvent], *, window_days: float = 1.0) -> dict[str, object]:
    """Time grazing versus resting, and how hard the herd is leaning on the line.

    Shares count only fixes with a reported activity. ``cues_past_line`` counts
    cues given after the animal crossed the line (negative margin), a sign the
    boundary is being tested rather than respected.
    """

    known = [fix.activity for fix in fixes if fix.activity]
    collars = {fix.collar_id for fix in fixes} | {cue.collar_id for cue in cues}
    collar_days = len(collars) * window_days if collars else 0
    grazing = sum(1 for activity in known if activity == "grazing")
    resting = sum(1 for activity in known if activity in {"resting", "lying", "ruminating"})
    return {
        "grazing_share": round(grazing / len(known), 3) if known else None,
        "resting_share": round(resting / len(known), 3) if known else None,
        "cue_count": len(cues),
        "cues_per_collar_day": round(len(cues) / collar_days, 2) if collar_days else None,
        "cues_past_line": sum(1 for cue in cues if cue.margin_meters is not None and cue.margin_meters < 0),
    }
