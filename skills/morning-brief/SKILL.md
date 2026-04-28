---
name: morning-brief
description: Generate the daily farm summary and recommendation.
version: 1.0.0
---
# Morning Brief

## When to Use

Use this skill when the farmer asks for today's state of the farm or when the daily briefing workflow triggers automatically.

## Procedure

1. Establish current farm context.
2. Review the latest observations.
3. Retrieve the most relevant practitioner knowledge.
4. Determine whether the right action is `MOVE`, `STAY`, or `NEEDS_INFO`.
5. Explain the recommendation plainly.
6. Request the single most useful additional observation when uncertainty is material.

## Pitfalls

- Do not present confidence without reasons.
- Do not hide stale or missing observations.
- Do not ask for many follow-ups at once.

## Verification

A good brief states what is true, what should happen, why, and what would help next.
