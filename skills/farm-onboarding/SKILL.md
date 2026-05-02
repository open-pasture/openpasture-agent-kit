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
3. Capture the farm name, timezone, first herd, and at least one paddock before ending onboarding.
4. Set the herd's current paddock before generating the first morning brief.
5. Accept flexible geospatial input such as screenshots, rough polygons, landmarks, and map clues.
6. Convert those inputs into structured farm and paddock geometry when possible.
7. When map screenshots, survey sketches, or farmer-drawn boxes are involved, load the `geo-onboarding` skill and persist draft boundaries with `save_geo_onboarding_draft`.
8. If geometry is still uncertain, preserve the remaining location clues in onboarding notes rather than inventing precise coordinates.
9. After setup is complete, switch back to normal daily operations and keep setup tools in the background.

## Success Criteria

The agent can produce a first morning brief from the information gathered, and the stored farm state is stable enough that later chats can focus on observations and grazing decisions instead of redoing setup.
