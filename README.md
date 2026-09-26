# Openpasture Agent Kit

This repository is the `Openpasture` engine: the data and decision layer between what the world knows about the land and the collars that move the herd.

- **Alexandria** takes a point or polygon and returns what is known about it: current, historical, and forecast weather, satellite imagery, drought and climate history, hazards, soil, vegetation, species, water, and terrain, each with sources. It also carries the grazing knowledge: research papers, practitioner videos, and hands-on wisdom from graziers like Greg Judy.
- **OpenCollar** collars report each animal's position and accept versioned boundary commands.

Every decision window, daily by default, for every herd, the engine answers one question: should the herd move today, and if so, where?

1. It assembles collar positions, a land report for the current paddock and the candidates, the farm's grazing history, and relevant knowledge.
2. It derives grazing signals: pressure, rest, forage, recovery, feed budget, and weather risk.
3. An agent reasons over that context through tools and skills and decides `STAY`, `MOVE` to a specific boundary, or `NEEDS_INFO`, with reasoning, a confidence, and the one observation that would help most.
4. The farmer's autonomy setting decides what happens next: `propose` (the default, waits for approval), `apply_unless_stopped`, or `apply`.
5. The boundary goes to the collars, and the engine records which collars confirmed it.
6. On later cycles, the engine evaluates what happened and writes the outcome back to the decision.

The decision record is the core asset: every decision, the inputs behind it, the farmer's response, the boundary sent, and the outcome. The farmer stays the operator. An override is recorded as signal, never treated as an error.

The farm view (map, decision timeline, paddock history, analytics) lives in `openpasture-cloud` and reads the decision record through this kit. This repo runs on its own, self-hosted, without the cloud product.

## Runtime Modes

The engine is packaged as an agent kit. The richest runtime is a coding agent with CLI access, skills, files, and code execution.

- **Coding-agent mode:** a coding agent reads skills, runs the `openpasture` CLI, inspects files and state, and runs decisions directly in a workspace.
- **MCP client mode:** ChatGPT, Claude, Cursor, and other MCP-capable clients reach the same tools and skills through the MCP connector.
- **Hermes adapter:** preserves the existing Hermes plugin entry point.

## What Works Now

- SQLite-backed farm, land unit, herd, observation, decision, and knowledge storage
- Optional Convex-backed farm state through `OPENPASTURE_STORE=convex`
- First-run farm onboarding, map-based geo onboarding, collar linking, and autonomy setup
- The decision cycle: `run_decision_cycle` assembles context, gets a decision, applies autonomy, sends the boundary, and records it
- Grazing decisions (`STAY`, `MOVE`, `NEEDS_INFO`) with inputs, farmer response, boundary command, and outcome on the record
- A heuristic fallback that decides when no agent brain is available
- `generate_morning_brief`, the farmer-readable wrapper of the latest decision, with recurring local scheduling
- Knowledge search over the curated `seed/` corpus and stored lessons, with Alexandria as the primary source when configured, plus lesson storage and batch ingestion
- Data pipelines for other vendor systems
- Portable skill discovery

Both outside connectors ship with stand-ins, so the whole loop runs offline:

- **Land reports** come from Alexandria when `FIRECRAWL_API_KEY` is set. Without it, an open-data fallback fills weather and marks imagery unavailable. An offline fixture source exists for tests and demos.
- **Collars** ship with a simulated gateway and an HTTP gateway adapter. The default is `simulated`: positions and confirmations are made up and nothing reaches a real collar.

## Quickstart

```bash
pip install "git+https://github.com/NousResearch/hermes-agent.git@1cec910b6a064d4e4821930be5cfaaf6145a2afd"
pip install -e .

export OPENPASTURE_STORE=sqlite
export OPENPASTURE_DATA_DIR="$HOME/.openpasture"
export OPENPASTURE_BRIEF_TIME="06:00"
# Optional: real Alexandria land reports and knowledge, and web ingestion.
export FIRECRAWL_API_KEY="fc-..."
# Collars: simulated by default. Use http with a gateway URL for real collars.
export OPENPASTURE_COLLAR_GATEWAY=simulated
```

Optional Convex backend:

```bash
npm install
npx convex dev
npx convex env set OPENPASTURE_CONVEX_STORE_KEY "replace-with-a-long-random-secret"

export OPENPASTURE_STORE=convex
export OPENPASTURE_CONVEX_URL="https://your-deployment.convex.cloud"
export OPENPASTURE_CONVEX_KEY="replace-with-a-long-random-secret"
```

Use the CLI:

```bash
openpasture tools list
openpasture skills list
openpasture tool run setup_initial_farm --json '{"name":"Willow Creek","timezone":"America/Chicago","herd":{"id":"herd_1","species":"cattle","count":28},"paddocks":[{"id":"paddock_home","name":"Home","status":"grazing"}]}'
openpasture tool run set_autonomy --json '{"herd_id":"herd_1","autonomy":"propose"}'
openpasture tool run run_decision_cycle --json '{"herd_id":"herd_1"}'
openpasture tool run list_decisions --json '{"herd_id":"herd_1"}'
openpasture tool run generate_morning_brief --json '{}'
```

Arguments shown are the common case. Run `openpasture tools list` for each tool's exact schema.

Use Hermes:

```bash
hermes gateway setup
hermes chat
```

Run the MCP connector:

```bash
python -m openpasture.connectors.mcp
```

## Project Shape

```text
src/openpasture/
  context.py           Runtime-agnostic kit context
  toolkit.py           Framework-neutral tool catalog
  connectors/          Hermes and MCP adapters
  cli.py               Agent-friendly JSON CLI
  plugin.py            Hermes compatibility shim
  domain/              Core farm primitives
  tools/               Dict-in, JSON-out tool handlers
  store/               Storage protocols and backends
  knowledge/           Seed loading, embeddings, retrieval, ingestion batches
  ingestion/           External farm signal pipelines
  briefing/            Decision context assembly, heuristic fallback, scheduling
skills/                Portable operational runbooks
seed/                  Foundational grazing knowledge
SOUL.md                Agent voice and operating philosophy
```

## Docs Site

The public Mintlify docs live in `docs-site/`. They adapt the existing source
docs into a reader-facing site while keeping this repo as the canonical source
for voice, mission, boundaries, and agent guidance.

Preview locally:

```bash
cd docs-site
npx mint@latest dev
```

Validate the docs config and links:

```bash
cd docs-site
npx mint@latest broken-links
```

Deploying the hosted Mintlify site requires a Mintlify account or connected Git
provider. For a GitHub-backed deployment, install the Mintlify GitHub App on the
docs repository from the Mintlify dashboard and set the docs subdirectory to
`docs-site`. Do not store tokens or account credentials in this repo.

## Maintainer Validation

```bash
uv run --python 3.11 pytest
uv run --python 3.11 openpasture-alpha-validate automated
uv run --python 3.11 openpasture validate alpha automated
```

## Boundary

This repository owns the engine: domain model, decision record, calculations, land and collar connectors, tools, skills, and knowledge access. Hosted accounts, the farm view, notifications, billing, and support live in `openpasture-cloud` and wrap this kit instead of replacing it. Collar hardware, firmware, and the collar protocol live in `opencollar`.
