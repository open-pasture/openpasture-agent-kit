# AGENTS.md

This file is the primary reference for coding agents working on `openPasture`.

Read `docs/vision.md` first, then `docs/architecture.md`.

## Core Principle

The agent is the product.

The open-source Hermes plugin is the primary artifact. Hosted infrastructure, dashboards, billing, and provisioning are secondary wrappers around the same primitive.

## Core User Flow

1. Farmer messages the agent in the morning.
2. The agent assembles current farm context.
3. The agent issues a morning brief.
4. The brief recommends `MOVE`, `STAY`, or `NEEDS_INFO`.
5. The agent asks for the single most useful field observation when uncertainty is high.
6. Farmer feedback becomes future context.

## Repository Map

- `src/openpasture/domain/`: pure domain primitives with no framework coupling.
- `src/openpasture/tools/`: Hermes-callable tools and schemas.
- `src/openpasture/store/`: storage protocol plus backend implementations.
- `src/openpasture/knowledge/`: transcript ingestion, extraction, embeddings, retrieval.
- `src/openpasture/ingestion/`: weather, satellite, and photo pipelines.
- `src/openpasture/briefing/`: morning brief assembly and scheduling.
- `skills/`: Hermes skills for reusable operational patterns.
- `seed/`: durable foundational knowledge.

## Architectural Rules

- Keep behavior in the agent whenever self-hosting remains possible.
- Treat storage as an interchangeable backend behind `FarmStore`.
- Keep domain objects framework-agnostic.
- Prefer plain language and farmer legibility over clever abstractions.
- Avoid speculative UI-first abstractions in this repository.

## Domain Glossary

- `Farm`: the root operational unit.
- `Paddock`: a grazeable land unit within a farm.
- `Herd`: a livestock group under one management decision.
- `Observation`: any time-bound signal about the farm.
- `MovementDecision`: the recommendation for the current decision window.
- `KnowledgeEntry`: a structured lesson extracted from a trusted source.

## Questions To Ask Before Building

1. Does this help the morning brief loop?
2. Can a self-hosted farmer use this without the hosted platform?
3. Is the output understandable to a farmer in plain language?
4. Are we preserving the agent as the core primitive?
5. Can this be expressed as a tool, skill, or domain object instead of a bespoke service?
