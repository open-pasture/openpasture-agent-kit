# Self-Hosting

`Openpasture` is designed to be usable without the hosted platform.

This repository is the open-source engine. Hermes is the most validated
self-hosted runtime today, but the CLI and MCP connectors run the same tools.
The hosted Openpasture product wraps this logic from a separate cloud
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
export OPENPASTURE_COLLAR_GATEWAY=simulated
```

Additional provider-specific variables depend on your chosen LLM and telemetry stack.

`OPENPASTURE_BRIEF_TIME` controls the local scheduled morning brief time in `HH:MM` 24-hour format. The runtime schedules one recurring brief job per farm using the farm's timezone.

`FIRECRAWL_API_KEY` is used for two things: Alexandria land reports and knowledge, and the knowledge-ingestion workflow, which uses Firecrawl search, scrape, and interact to read external sources. If it is missing, onboarding, decisions, and morning briefs still work. Land reports fall back to offline fixtures, and external ingestion tools return a clear error.

## Land And Collars

The decision cycle needs two outside connectors. Both ship with stand-ins so a
self-hosted install runs end to end without hardware or accounts.

- **Land reports.** The Alexandria adapter fetches real reports for your
  paddock geometry. Without a key, an open-data fallback
  fills weather and marks imagery unavailable. The fixture source returns canned
  reports for offline work and tests. Pick with `OPENPASTURE_LAND_SOURCE`.
- **Collars.** `OPENPASTURE_COLLAR_GATEWAY=simulated` (the default) simulates
  positions and boundary confirmations. Nothing reaches a real collar.
  `OPENPASTURE_COLLAR_GATEWAY=http` with `OPENPASTURE_COLLAR_GATEWAY_URL`
  sends boundary commands to a collar gateway and reads acknowledgements
  back.

Keep the herd's autonomy at `propose` while you test. Switch the gateway to
`http` only when you mean for boundaries to reach real animals.

See `docs-site/environment-variables.mdx` for the full variable table.

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

During this first-run flow, `Openpasture` treats setup as a constrained onboarding workflow.

- The preferred setup primitive is `setup_initial_farm`.
- One farm per instance is the default alpha behavior.
- Additional farm creation is reserved for rare admin cases via an explicit override.
- Farmers can provide rough geospatial input such as screenshots, boundaries, landmarks, and map clues; the agent should convert those into structured geometry when possible and keep unresolved location context in notes.

After onboarding, a good second prompt is:

```text
Record this observation for the current paddock: forage is getting short and muddy near the water point. Then run today's grazing decision for the herd.
```

## First-Run Behavior

- `Openpasture` creates local `farm.db` and `knowledge.db` files under `OPENPASTURE_DATA_DIR`.
- If `knowledge.db` is empty on first run, the agent auto-loads the seed knowledge in `seed/principles/`.
- Set `OPENPASTURE_LOAD_SEED=0` to force-skip that bootstrap.
- Set `OPENPASTURE_LOAD_SEED=1` to force a seed reload.

## Storage Modes

- `sqlite`: default self-hosted mode.
- `convex`: optional first-party backend for hosted or self-hosted runtimes that
  want managed sync and real-time UI reads.

### Optional Convex Backend

Convex is not required for self-hosting. Use it when you want a managed backend
instead of local SQLite files.

From the agent kit repo:

```bash
npm install
npx convex dev
npx convex env set OPENPASTURE_CONVEX_STORE_KEY "replace-with-a-long-random-secret"
```

Then run the Openpasture agent against that deployment:

```bash
export OPENPASTURE_STORE=convex
export OPENPASTURE_CONVEX_URL="https://your-deployment.convex.cloud"
export OPENPASTURE_CONVEX_KEY="replace-with-a-long-random-secret"
```

The Convex backend files live in `convex/`. They store portable farm state only:
farm structure, observations, grazing decisions, pipelines, and daily briefs. Hosted account systems such as Clerk, invites, billing,
provisioning, and support remain outside the OSS backend.

## Current Alpha Boundaries

- The self-hosted alpha defaults to SQLite, local scheduling, and Hermes messaging.
- Land reports fall back to open data (weather only) until Alexandria is configured.
- Collars default to the simulated gateway. The HTTP gateway adapter is new and
  has not been validated against a fleet of real collars.
- Photo ingestion is not implemented yet.
- The farm view (map and decision timeline) is part of the hosted product.
  Self-hosted farmers read and answer decisions through conversation or the CLI.
- `convex` is available as an optional backend, but SQLite remains the simplest
  path for local single-farm installs.
- Scheduled brief delivery remains local to this runtime. Hosted transport and delivery orchestration belong in the separate cloud wrapper.

## Maintainer Pilot Validation

If you are validating two operator-managed pilot instances on one machine, use Hermes profiles and the reusable runbook in [`docs/alpha-validation.md`](alpha-validation.md).

## Hardware Notes

The initial personal testing target is a laptop or small VPS. Collar fixes are the highest-volume data; raw fixes are kept for a retention window and rolled into summaries, so a small machine is enough for one farm.
