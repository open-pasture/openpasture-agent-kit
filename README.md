# openPasture Agent Kit

This repository contains the agent kit for `openPasture`, the agent-native farm operating toolkit for pasture-based livestock management.

`openPasture` is the product suite. This repo packages the portable agent-facing kit: tools, skills, farm state, knowledge, connector adapters, and operating opinions that can bolt onto an agent brain. The richest runtime is a coding agent with CLI access, skills, files, and code execution. MCP is a supported integration method for chat assistants and other MCP-capable clients. Hermes remains one supported adapter.

## Product Thesis

The farmer brings a conversation surface. The agent brings reasoning. `openPasture` brings the farming domain:

- executable tools for farm setup, observations, plans, knowledge, and data pipelines,
- portable markdown skills that teach an agent how to work through farm operations,
- curated practitioner knowledge from trusted regenerative agriculture sources,
- local-first farm state backed by SQLite by default,
- ingestion paths for weather, satellite, photos, and vendor telemetry,
- a plain-language operating stance encoded in `SOUL.md`.

The goal is to turn any capable general agent into a useful companion for managing a pasture-based livestock farm alongside the farmer.

## Runtime Modes

- **Coding-agent mode:** a coding agent reads skills, runs the `openpasture` CLI, inspects files/state, and composes farm workflows directly in a workspace.
- **MCP client mode:** ChatGPT, Claude, Cursor, and other MCP-capable clients access the same tools and skills through the MCP connector.
- **Hermes adapter:** preserves the existing Hermes plugin entry point.

## What Works Now

- SQLite-backed farm, paddock, herd, observation, plan, and knowledge storage
- First-run farm onboarding
- Seed knowledge bootstrap
- Knowledge search and lesson storage
- Morning brief generation with `MOVE`, `STAY`, or `NEEDS_INFO`
- Recurring local morning-brief scheduling
- Data pipeline setup, persistence, and execution
- Portable skill discovery

## Quickstart

```bash
pip install "git+https://github.com/NousResearch/hermes-agent.git@1cec910b6a064d4e4821930be5cfaaf6145a2afd"
pip install -e .

export OPENPASTURE_STORE=sqlite
export OPENPASTURE_DATA_DIR="$HOME/.openpasture"
export OPENPASTURE_BRIEF_TIME="06:00"
# Optional, required for external web knowledge ingestion:
export FIRECRAWL_API_KEY="fc-..."
```

Use the CLI:

```bash
openpasture tools list
openpasture skills list
openpasture tool run setup_initial_farm --json '{"name":"Willow Creek","timezone":"America/Chicago","herd":{"id":"herd_1","species":"cattle","count":28},"paddocks":[{"id":"paddock_home","name":"Home","status":"grazing"}]}'
openpasture tool run generate_morning_brief --json '{}'
```

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
  briefing/            Farm context assembly, default advisor, scheduling
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

This repository owns the portable agent kit for the openPasture farm operating toolkit. Hosted infrastructure, billing, account management, proprietary UI, and support workflows should wrap this kit instead of replacing it.
