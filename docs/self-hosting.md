# Self-Hosting

`openPasture` is designed to be usable without the hosted platform.

## What You Need

- Python 3.11+
- a supported Hermes installation
- an LLM provider key
- a messaging platform account such as Telegram

## Installation

```bash
pip install "git+https://github.com/NousResearch/hermes-agent.git"
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

## Hardware Notes

The initial personal testing target is a laptop or small VPS. The first milestone is a useful messaging-first workflow, not high-throughput infrastructure.
