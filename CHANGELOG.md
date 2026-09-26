# Changelog

## Unreleased

Openpasture is now framed and built as the grazing decision engine between Alexandria (land reports and grazing knowledge) and OpenCollar (herd positions and boundary control).

- added the decision cycle: every decision window (daily by default), each herd gets a `GrazingDecision` of `STAY`, `MOVE` to a specific boundary, or `NEEDS_INFO`, with reasoning, confidence, inputs, farmer response, boundary command, and outcome on one record
- added farmer autonomy settings per herd: `propose` (default), `apply_unless_stopped`, and `apply`, set with `set_autonomy`
- added decision tools: `assemble_decision_context`, `compute_grazing_signals`, `submit_grazing_decision`, `respond_to_decision`, `get_decision`, `list_decisions`, `evaluate_decision_outcome`, and `run_decision_cycle`
- added the land connector and `get_land_report`, with an offline fixture provider and an Alexandria adapter
- added the collar connector with `record_collar_report`, `get_herd_positions`, and `get_boundary_status`, with a simulated gateway (default) and an HTTP gateway adapter
- renamed `MovementDecision` to `GrazingDecision`
- removed `movement_decision` and `approve_plan`; use `submit_grazing_decision` and `respond_to_decision`
- kept `generate_morning_brief` as the farmer-readable wrapper of the latest decision
- added the `daily-grazing-decision` skill and updated onboarding, brief, rotation, pasture, knowledge, and pipeline skills to match
- rewrote `SOUL.md`, the README, `docs/`, and the docs site around the engine; added docs-site pages for the decision engine, land reports, and collars

## 0.1.0-alpha

- verified the real Hermes connector path with an end-to-end smoke run that creates a farm, records an observation, generates a morning brief, and searches knowledge
- added Hermes-compatible tool wrappers so plugin tools work when Hermes injects metadata like `task_id`
- implemented recurring morning-brief scheduling with `apscheduler` and runtime wiring for farm bootstrap and delivery injection
- changed seed knowledge loading to bootstrap automatically on first run, with explicit skip and reload controls through `OPENPASTURE_LOAD_SEED`
- hardened the alpha runtime around missing `FIRECRAWL_API_KEY`, weather API failures, and clearer session-time notices for incomplete configuration
- updated self-hosting and README docs to reflect the current alpha workflow, included skills, and known limitations
- documented the OSS/cloud repository boundary, current cloud handoff baseline, and maintainer validation expectations
