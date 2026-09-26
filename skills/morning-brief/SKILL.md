---
name: morning-brief
description: Deliver the farmer-readable morning summary built on the latest grazing decision for each herd.
version: 2.0.0
---
# Morning Brief

## When to Use

Use this skill when the farmer asks for today's state of the farm or when the
daily brief triggers automatically.

The brief is not a second decision. It wraps the latest `GrazingDecision` for
each herd in plain language. If today's decision has not been made yet, make it
first with the `daily-grazing-decision` skill or `run_decision_cycle`.

## Procedure

1. Call `list_decisions` for the current window, or `get_decision` for one
   herd, to find today's decision.
2. If there is none for a herd, run the `daily-grazing-decision` skill first.
3. Call `generate_morning_brief` to produce the brief from the stored
   decisions and farm state.
4. For each herd, lead with the call: `STAY`, `MOVE` to which paddock, or
   `NEEDS_INFO`.
5. Say where the decision stands:
   - waiting for your approval,
   - will be sent at a set time unless you stop it,
   - sent, with how many collars confirmed (`get_boundary_status`).
6. Give the two to four reasons from the decision. Do not add new ones that are
   not on the record.
7. Name anything stale or missing: old imagery, quiet collars, no recent field
   note.
8. If the decision carries an observation request, ask for that one thing.
9. If a past decision was evaluated since the last brief, mention the outcome
   in one line when it matters.

## Pitfalls

- Do not present confidence without reasons.
- Do not hide stale or missing data.
- Do not ask for many follow-ups at once.
- Do not say the herd moved when the boundary is only proposed or unconfirmed.

## Verification

A good brief states what the herd should do today, why, whether anything was
sent to the collars, and what would help next.
