# Self-Hosting

`openPasture` is designed to be usable without the hosted platform.

This repository is the Hermes-specific implementation of the OSS agent core.
The hosted OpenPasture product should wrap this logic from a separate cloud
repository instead of moving hosted concerns into this repo. See
[`cloud-boundary.md`](cloud-boundary.md) for the architectural split.

## What You Need

- Python 3.11+
- a supported Hermes installation
- an LLM provider key
- a messaging platform account such as Telegram

## Installation

```bash
pip install "git+https://github.com/NousResearch/hermes-agent.git@1cec910b6a064d4e4821930be5cfaaf6145a2afd"
pip install -e .
```

## Recommended Environment Variables

```bash
export OPENPASTURE_STORE=sqlite
export OPENPASTURE_DATA_DIR="$HOME/.openpasture"
export OPENPASTURE_DEFAULT_TIMEZONE="America/Chicago"
export OPENPASTURE_BRIEF_TIME="06:00"
export OPENPASTURE_LLM_PROVIDER="anthropic"
export FIRECRAWL_API_KEY="fc-..."
```

Additional provider-specific variables depend on your chosen LLM and telemetry stack.

`OPENPASTURE_BRIEF_TIME` controls the local scheduled morning brief time in `HH:MM` 24-hour format. The runtime schedules one recurring brief job per farm using the farm's timezone.

`FIRECRAWL_API_KEY` is required for the knowledge-ingestion workflow because the agent uses Firecrawl search, scrape, and interact to discover and read external sources. If it is missing, onboarding and morning briefs still work, but external ingestion tools will return a clear error.

## Messaging Setup

Use Hermes to connect the messaging platform you want to test with first.

```bash
hermes gateway setup
```

For initial personal testing, Telegram is the simplest path because it supports text, images, and a straightforward bot flow.

## First Session

After Hermes is configured:

```bash
hermes
```

Suggested first prompt:

```text
I am setting up a new pasture-based livestock farm. Help me create the farm, paddocks, and first herd.
```

During this first-run flow, `openPasture` treats setup as a constrained onboarding workflow.

- The preferred setup primitive is `setup_initial_farm`.
- One farm per instance is the default alpha behavior.
- Additional farm creation is reserved for rare admin cases via an explicit override.
- Farmers can provide rough geospatial input such as screenshots, boundaries, landmarks, and map clues; the agent should convert those into structured geometry when possible and keep unresolved location context in notes.

After onboarding, a good second prompt is:

```text
Record this observation for the current paddock: forage is getting short and muddy near the water point. Then give me today's morning brief.
```

## First-Run Behavior

- `openPasture` creates local `farm.db` and `knowledge.db` files under `OPENPASTURE_DATA_DIR`.
- If `knowledge.db` is empty on first run, the agent auto-loads the seed knowledge in `seed/principles/`.
- Set `OPENPASTURE_LOAD_SEED=0` to force-skip that bootstrap.
- Set `OPENPASTURE_LOAD_SEED=1` to force a seed reload.

## Storage Modes

- `sqlite`: default self-hosted mode.
- `convex`: intended for the hosted wrapper and dashboards.

## Current Alpha Boundaries

- The self-hosted alpha is built around SQLite, local scheduling, and Hermes messaging.
- Satellite ingestion and photo ingestion are not implemented yet.
- `convex` is reserved for the later hosted wrapper and is not ready for production use in this repo yet.
- Scheduled brief delivery remains local to this runtime. Hosted transport and delivery orchestration belong in the separate cloud wrapper.

## Maintainer Pilot Validation

If you are validating two operator-managed pilot instances on one machine, use Hermes profiles and the reusable runbook in [`docs/alpha-validation.md`](alpha-validation.md).

## Hardware Notes

The initial personal testing target is a laptop or small VPS. The first milestone is a useful messaging-first workflow, not high-throughput infrastructure.
