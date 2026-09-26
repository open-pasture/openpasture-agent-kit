---
name: farm-onboarding
description: Run the constrained first-run onboarding workflow for one farm, including herd-to-collar linking and the farmer's autonomy setting.
version: 2.0.0
---
# Farm Onboarding

## When to Use

Use this skill when a farmer is setting up `Openpasture` for the first time.

Treat onboarding as a special workflow, not the normal daily operating mode.

## Procedure

### Farm, Herd, Paddocks

1. Create exactly one farm for the instance unless the operator explicitly asks for an admin override.
2. Prefer `setup_initial_farm` for the common first-run path.
3. If a farm already exists for the instance, use onboarding to refine that farm's name, timezone, location, herds, and paddocks instead of trying to create a second farm.
4. Capture the farm name, timezone, first herd, and at least one paddock before ending onboarding.
5. Set the herd's current paddock before the first decision.
6. Accept flexible geospatial input such as screenshots, rough polygons, landmarks, and map clues.
7. Convert visible coordinates into a structured `location` object when possible. A screenshot or `location_hint` alone preserves notes, but it does not update the farm point.
8. Convert boundary and paddock clues into structured geometry when possible. The engine needs paddock geometry to request land reports and to send boundaries.
9. When map screenshots, survey sketches, or farmer-drawn boxes are involved, load the `geo-onboarding` skill and persist draft boundaries with `save_geo_onboarding_draft`.
10. If geometry is still uncertain, preserve the remaining location clues in onboarding notes rather than inventing precise coordinates.

### Collars

11. Ask whether the herd wears virtual-fence collars. If not, skip this part. The engine still decides, and the farmer moves the herd by hand.
12. If yes, record which collar IDs belong to which herd. Every collar on the herd should be linked, or confirmations will look incomplete.
13. Confirm the link with `get_herd_positions`. If no fixes come back, say so plainly and check the gateway setting before going further.
14. Be clear about the gateway. With `OPENPASTURE_COLLAR_GATEWAY=simulated` (the default), positions and confirmations are simulated and nothing reaches real collars.

### Autonomy

15. Explain the three settings in plain words and let the farmer choose with `set_autonomy`:
    - `propose` (default): every move waits for your approval.
    - `apply_unless_stopped`: a move is sent at a set time unless you stop it first.
    - `apply`: moves are sent when decided, and you review after.
16. Recommend starting with `propose` until the farmer has seen a few weeks of decisions and trusts them. Do not push a higher setting.

### Finish

17. Run the first decision with the `daily-grazing-decision` skill so the farmer sees what a decision looks like.
18. After setup is complete, switch back to normal daily operations and keep setup tools in the background.

## Success Criteria

The engine can make a first grazing decision from the stored state. The herd's
collars are linked or clearly marked as not in use. The farmer knows which
autonomy setting is on and what it means. Later chats can focus on decisions
and observations instead of redoing setup.
