# openPasture

`openPasture` is an open-source grazing management companion built as a Hermes agent plugin.

It helps pasture-raised livestock farmers reason about daily movement decisions by combining:

- practitioner knowledge from trusted regenerative farmers,
- farm-specific context such as paddocks, herd state, and observations,
- operational inputs like weather, satellite imagery, and farmer notes,
- a conversational interface that works over messaging platforms.

The agent is the product. The hosted offering is a wrapper around the same core.

## What It Does

- stores farms, paddocks, herd position, and observations in local SQLite,
- uses a preferred first-run onboarding workflow to create the initial farm state,
- auto-loads foundational grazing knowledge on first run,
- ingests curated grazing knowledge from YouTube transcripts and structured notes,
- stores farm geometry, herd state, and observations,
- generates a morning brief with a move, stay, or ask-for-more-information recommendation,
- schedules a recurring morning-brief job inside the agent runtime,
- directs farmer attention toward the single observation that would reduce uncertainty most,
- remains usable as a fully self-hosted open-source tool.

## Quickstart

1. Install Hermes Agent.
2. Install `openPasture`.
3. Configure the alpha environment.
4. Start talking to the agent.

```bash
pip install "git+https://github.com/NousResearch/hermes-agent.git@1cec910b6a064d4e4821930be5cfaaf6145a2afd"
pip install -e .
export OPENPASTURE_STORE=sqlite
export OPENPASTURE_DATA_DIR="$HOME/.openpasture"
export OPENPASTURE_BRIEF_TIME="06:00"
# Optional, but required for external knowledge ingestion:
export FIRECRAWL_API_KEY="fc-..."

hermes gateway setup
hermes chat
```

`openPasture` will bootstrap `farm.db`, `knowledge.db`, and seed knowledge on first run. If `FIRECRAWL_API_KEY` is missing, the agent still works for farm setup, observations, and morning briefs, but external knowledge ingestion stays disabled.

## Alpha Walkthrough

1. Start with onboarding:

```text
I am setting up a new pasture-based livestock farm. Help me create the farm, paddocks, and first herd.
```

2. Add a real field note after setup:

```text
Record this observation for the current paddock: forage is getting short and muddy near the water point.
```

3. Ask for the day's recommendation:

```text
Give me today's morning brief.
```

4. If you want to expand the ancestral knowledge base, add `FIRECRAWL_API_KEY` and use the knowledge-ingestion workflow to curate trusted sources.

## Onboarding Mode

First-run setup is treated as a special workflow instead of a permanently open-ended daily capability.

- `setup_initial_farm` is the preferred onboarding primitive.
- One farm per instance is the default alpha behavior.
- Extra farm creation requires an explicit admin override.
- Farmers can still describe land flexibly with map screenshots, rough boundaries, and landmarks; the agent should convert those inputs into structured geometry when possible and keep any unresolved clues in notes.

## Included Skills

- `farm-onboarding`: conversational setup of farm, paddocks, and herd state
- `morning-brief`: daily `MOVE` / `STAY` / `NEEDS_INFO` recommendation flow
- `pasture-assessment`: reconcile field notes with remote or indirect signals
- `rotation-planning`: near-term movement reasoning with practical constraints
- `knowledge-ingestion`: Firecrawl-assisted curation of trusted practitioner sources

## Project Shape

```text
src/openpasture/
  plugin.py          Hermes plugin entry point
  domain/            Core domain primitives
  tools/             Agent-callable tools
  store/             Storage abstraction and backends
  knowledge/         Knowledge ingestion and retrieval pipeline
  ingestion/         External observation pipelines
  briefing/          Morning brief assembly and scheduling
skills/              Hermes skills used by the agent
seed/                Foundational grazing knowledge
```

## Development Stance

This repository biases strongly toward the agent.

If a capability can live inside the open-source agent and still support self-hosting, it belongs here. The hosted platform should only make provisioning easier and layer account, billing, and dashboard functionality on top.

## Status

This repository is ready for a simple self-hosted alpha.

What works now:

- real Hermes plugin registration and tool calling
- SQLite-backed farm and knowledge storage
- first-run seed knowledge bootstrap
- weather-assisted morning brief generation
- recurring morning-brief scheduling inside the runtime
- knowledge search and structured lesson storage

What comes after alpha:

- `ConvexStore` for the hosted cloud data plane
- satellite ingestion
- photo ingestion
- knowledge release packaging and signed update flow

## Known Limitations

- `ConvexStore` is still a stub, so hosted/cloud mode is not ready yet.
- Satellite and photo ingestion are not implemented yet.
- Scheduled brief delivery stays local to the Hermes runtime in this repo. Hosted transport orchestration still belongs in the separate cloud wrapper.
- External web knowledge ingestion requires `FIRECRAWL_API_KEY`.

## Maintainer Validation

Use the reusable alpha harness after Hermes updates or plugin changes:

```bash
uv run --python 3.11 openpasture-alpha-validate automated
uv run --python 3.11 openpasture-alpha-validate docker
```

For the full two-profile pilot validation flow, see [`docs/alpha-validation.md`](docs/alpha-validation.md).
