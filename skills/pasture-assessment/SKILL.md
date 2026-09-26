---
name: pasture-assessment
description: Assess pasture condition from field notes, photos, collar pressure, and land report imagery.
version: 2.0.0
---
# Pasture Assessment

## When to Use

Use this skill when interpreting current pasture condition, estimating
residual or recovery, or reconciling conflicting inputs. The daily decision
leans on it.

## Procedure

1. Gather the latest farmer observations for the paddock.
2. Call `get_land_report` with the `imagery` section for the paddock. Note the
   capture date and cloud cover.
3. Call `compute_grazing_signals` for grazing pressure and recovery history.
4. Distinguish direct field observations from inferred remote signals.
5. Look for forage sufficiency, stress, and recovery patterns. Compare against
   how this paddock recovered last time.
6. Check the `vegetation` section for invasive or toxic plants when the herd
   is heading somewhere new.
7. State what remains uncertain and what single observation would settle it.

## Pitfalls

- Do not confuse biomass proxies like NDVI with exact grass height.
- Do not over-trust imagery when a recent field note contradicts it.
- Do not treat stale or cloudy imagery as current.
- Collar pressure tells you where the animals spent time, not what they ate.
