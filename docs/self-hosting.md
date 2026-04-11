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
export OPENPASTURE_LLM_PROVIDER="anthropic"
```

Additional provider-specific variables depend on your chosen LLM and telemetry stack.

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

## Storage Modes

- `sqlite`: default self-hosted mode.
- `convex`: intended for the hosted wrapper and dashboards.

## Hardware Notes

The initial personal testing target is a laptop or small VPS. The first milestone is a useful messaging-first workflow, not high-throughput infrastructure.
