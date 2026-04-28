# AGENTS.md

This file is the primary reference for coding agents working on the `openPasture` agent kit.

Read `docs/vision.md` first, then `docs/architecture.md`.

## Core Principle

The coding agent is the core primitive. `openPasture` is the product suite. This repository is the portable agent kit that equips an agent with pasture-based livestock expertise, farm state, executable tools, skills, and integrations.

Hermes is one supported connector. It is not the product boundary.

## Core User Flow

1. Farmer chats with an agent through their preferred surface.
2. The agent uses openPasture tools, skills, and knowledge to assemble farm context.
3. The agent answers questions, records observations, or produces a morning brief.
4. Recommendations are `MOVE`, `STAY`, or `NEEDS_INFO`.
5. When uncertainty is high, the agent asks for the single most useful observation.
6. Farmer feedback becomes future context.

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
- `Paddock`: a grazeable land unit within a farm.
- `Herd`: a livestock group under one management decision.
- `Observation`: any time-bound signal about the farm.
- `MovementDecision`: the recommendation for the current decision window.
- `KnowledgeEntry`: a structured lesson extracted from a trusted source.
- `ToolSpec`: a framework-neutral executable farm capability.
- `OpenPastureContext`: the runtime-agnostic kernel for stores, knowledge, and config.

## Questions To Ask Before Building

1. Does this help an agent operate a pasture-based livestock farm?
2. Can a self-hosted farmer use this without the hosted platform?
3. Can this work through more than one connector?
4. Is the output understandable to a farmer in plain language?
5. Should this be a tool, skill, knowledge entry, or domain object?
