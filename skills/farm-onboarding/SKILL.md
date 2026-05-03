---
name: farm-onboarding
description: Run the constrained first-run onboarding workflow for one farm.
version: 1.0.0
---
# Farm Onboarding

## When to Use

Use this skill when a farmer is setting up `openPasture` for the first time.

Treat onboarding as a special workflow, not the normal daily operating mode.

## Procedure

1. Create exactly one farm for the instance unless the operator explicitly asks for an admin override.
2. Prefer `setup_initial_farm` for the common first-run path.
3. If a farm already exists for the instance, use onboarding to refine that farm's name, timezone, location, herds, and paddocks instead of trying to create a second farm.
4. Capture the farm name, timezone, first herd, and at least one paddock before ending onboarding.
5. Set the herd's current paddock before generating the first morning brief.
6. Accept flexible geospatial input such as screenshots, rough polygons, landmarks, and map clues.
7. Convert visible coordinates into a structured `location` object when possible. A screenshot or `location_hint` alone preserves notes, but it does not update the farm point.
8. Convert boundary and paddock clues into structured geometry when possible.
9. When map screenshots, survey sketches, or farmer-drawn boxes are involved, load the `geo-onboarding` skill and persist draft boundaries with `save_geo_onboarding_draft`.
10. If geometry is still uncertain, preserve the remaining location clues in onboarding notes rather than inventing precise coordinates.
11. After setup is complete, switch back to normal daily operations and keep setup tools in the background.

## Success Criteria

The agent can produce a first morning brief from the information gathered, and the stored farm state is stable enough that later chats can focus on observations and grazing decisions instead of redoing setup.
