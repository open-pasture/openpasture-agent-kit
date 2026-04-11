# openPasture

`openPasture` is an open-source grazing management companion built as a Hermes agent plugin.

It helps pasture-raised livestock farmers reason about daily movement decisions by combining:

- practitioner knowledge from trusted regenerative farmers,
- farm-specific context such as paddocks, herd state, and observations,
- operational inputs like weather, satellite imagery, and farmer notes,
- a conversational interface that works over messaging platforms.

The agent is the product. The hosted offering is a wrapper around the same core.

## What It Does

- ingests curated grazing knowledge from YouTube transcripts and structured notes,
- stores farm geometry, herd state, and observations,
- generates a morning brief with a move, stay, or ask-for-more-information recommendation,
- directs farmer attention toward the single observation that would reduce uncertainty most,
- remains usable as a fully self-hosted open-source tool.

## Quickstart

1. Install Hermes Agent.
2. Install `openPasture`.
3. Configure an LLM provider and messaging platform.
4. Start talking to the agent.

```bash
pip install "git+https://github.com/NousResearch/hermes-agent.git"
pip install -e .
hermes gateway setup
hermes
```

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

This repository is intentionally scaffold-first.

The documentation, package structure, and module contracts are in place so implementation can proceed without losing the architectural center of gravity.
