---
name: rotation-planning
description: Look ahead past today's decision. Sequence paddocks over the coming weeks against rest, recovery, forage, and the forecast.
version: 2.0.0
---
# Rotation Planning

## When to Use

Use this skill when the farmer asks about the next week or longer: "where are
they going after 4?", "will we run out of grass before fall?", "how do I get
through the dry spell?"

Today's call belongs to the `daily-grazing-decision` skill. This skill sets the
plan that daily decisions draw on. The plan is guidance, not a queue of
commands. Nothing reaches the collars except through a recorded decision.

## Procedure

1. Identify the herd, the current paddock, and every candidate paddock.
2. Call `compute_grazing_signals` for rest, recovery, forage, and the feed
   budget.
3. Call `list_decisions` for the herd's recent history. Read overrides and
   outcomes. They show how this land actually responds.
4. Call `get_land_report` for the forecast, drought, and hazard sections when
   the plan runs past a few days.
5. Check practical constraints: water, lanes, labor, calving or lambing
   paddocks, hay ground, and anything the farmer has excluded.
6. Bring in relevant knowledge with `search_knowledge`.
7. Lay out a simple sequence with rough days per paddock and the reason for
   the order.
8. Name the point where the plan breaks: "if we don't get rain by the 10th,
   5 and 6 will not be recovered in time."

## Heuristics

- Preserve residual.
- Base rest on recovery, not the calendar. Slow the rotation when growth
  slows.
- Read the farm's recovery history before trusting a generic rest period.
- Keep a reserve paddock or feed plan for weather you cannot predict.
- Read animals and pasture together.
- Favor simple, explainable plans over fragile optimization.
