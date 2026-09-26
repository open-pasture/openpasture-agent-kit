# AGENTS.md

This file is the primary reference for coding agents working anywhere in the
Openpasture project. The agent kit is the canonical source of truth for product
behavior, voice, boundaries, and agent instructions.

## Session Onboarding

Every new agent session should do this before changing code, docs, or copy:

1. `SOUL.md`
2. `docs/voice-and-boundaries.md`
3. `docs/vision.md`
4. `docs/architecture.md`
5. `docs/contracts.md`
6. The local `AGENTS.md` in the repository being changed, if one exists.

Then decide where the change belongs:

- Farm behavior, agent behavior, reusable tools, skills, knowledge, connectors,
  self-hosted workflows, and source-of-truth docs belong in this repository.
- Hosted accounts, auth, provisioning, billing, support, and proprietary UI
  belong in `openpasture-cloud`.
- Public positioning, pricing, and lead capture belong in `openpasture-web`.
- The public docs site in `docs-site/` should adapt canonical material from this
  repo; do not let docs-site pages become the only source for product rules.

If a future agent would need to know something again, write it here or in
`docs/` instead of leaving it only in chat context.

## Core Principle

Openpasture is the data and decision layer between Alexandria, which knows the
land, and OpenCollar, which knows where the animals are and moves them. Every
day, for every herd, the engine decides whether to move the herd and where, and
sends the answer to the collars. This repository is that engine, packaged as a
portable agent kit.

Hermes is one supported connector. It is not the product boundary.

## Voice And Product Boundary

This repository is the canonical public source of truth for Openpasture voice,
mission, tone, product boundaries, and agent instructions.

Use plain farmer-to-farmer language. Do not overclaim autonomy. The engine
decides and can move the herd, but only as far as the farmer's autonomy setting
allows. The farmer remains the operator, and an override is always recorded as
signal, never treated as an error.

Keep the repository split clear:

- `openpasture-agent-kit`: public open-core agent kit and shared farm behavior.
- `openpasture-cloud`: hosted revenue product, accounts, auth, provisioning,
  proprietary dashboard, billing, and support.
- `openpasture-web`: closed marketing site and public positioning.
- `opencollar`: collar hardware, firmware, and the collar protocol.

## Core User Flow

1. Each decision window, the engine assembles context: collar positions, an
   Alexandria land report, the farm's grazing history, and relevant knowledge.
2. The agent reasons over that context through tools and skills.
3. The decision is `STAY`, `MOVE` to a specific boundary, or `NEEDS_INFO`, with
   reasoning and confidence.
4. When uncertainty is high, the agent asks for the single most useful observation.
5. The farmer approves, modifies, or overrides, as their autonomy setting requires.
6. The boundary goes to the collars, and the outcome is recorded against the
   decision so it becomes future context.

## Repository Map

- `src/openpasture/context.py`: runtime-agnostic kit context.
- `src/openpasture/toolkit.py`: framework-neutral tool catalog.
- `src/openpasture/connectors/`: runtime adapters such as Hermes and MCP.
- `src/openpasture/cli.py`: JSON CLI for agents, scripts, and cron.
- `src/openpasture/domain/`: pure domain primitives with no framework coupling.
- `src/openpasture/tools/`: dict-in, JSON-out farm tools.
- `src/openpasture/store/`: storage protocols plus backend implementations.
- `src/openpasture/knowledge/`: extraction, embeddings, retrieval, and ingestion batches.
- `src/openpasture/ingestion/`: weather, satellite, photo, and vendor pipelines.
- `src/openpasture/briefing/`: farm context assembly, default advisor, and scheduling.
- `skills/`: portable operational runbooks.
- `seed/`: durable foundational knowledge.

## Architectural Rules

- Put farm-operating behavior in the toolkit, not in one connector.
- Keep connector code thin and runtime-specific.
- Treat storage as interchangeable behind `FarmStore` and `KnowledgeStore`.
- Keep domain objects framework-agnostic.
- Prefer plain language and farmer legibility over clever abstractions.
- Treat skills as portable curriculum, not runtime-specific artifacts.
- Avoid speculative UI-first abstractions in this repository.

## Domain Glossary

- `Farm`: the root operational unit.
- `Pasture`: a durable field or pasture inside a farm boundary.
- `Paddock`: a movable or semi-durable grazing subdivision inside a pasture.
- `Section`: an optional daily or temporary subdivision inside a paddock.
- `LandUnit`: the shared geospatial primitive behind pastures, paddocks, sections, and related map features.
- `Herd`: a livestock group under one management decision.
- `Observation`: any time-bound signal about the farm.
- `GrazingDecision`: the decision for one herd in one decision window, with inputs, farmer response, and outcome.
- `LandReport`: what Alexandria returns about a geometry, stored as observations with provenance.
- `BoundaryCommand`: a versioned boundary sent to a herd's collars.
- `Autonomy`: the farmer's setting for how far the engine may act without approval.
- `KnowledgeEntry`: a structured lesson extracted from a trusted source.
- `ToolSpec`: a framework-neutral executable farm capability.
- `OpenPastureContext`: the runtime-agnostic kernel for stores, knowledge, and config.

## Questions To Ask Before Building

1. Does this help an agent operate a pasture-based livestock farm?
2. Can a self-hosted farmer use this without the hosted platform?
3. Can this work through more than one connector?
4. Is the output understandable to a farmer in plain language?
5. Should this be a tool, skill, knowledge entry, or domain object?
