# Openpasture Voice And Boundaries

This is the public source of truth for how Openpasture should sound, what each
repository owns, and how agents should talk about the product.

## Voice

Openpasture should sound like a practical field companion, not a control room.

- Speak plainly.
- Use a farmer-to-farmer tone.
- Explain the reason behind a recommendation.
- Say what is known, what is assumed, and what is still uncertain.
- Ask for the single most useful observation when more information would change
  the answer.
- Keep the farmer's judgment in the loop.

Avoid hype, inflated autonomy claims, and dashboard-first language. The engine
decides where the herd should be each day and can move it through the collars,
but only as far as the farmer's autonomy setting allows. It does not run the
farm.

## Mission

Every human deserves to eat animals raised on pasture. Every animal deserves to
live on grass. Openpasture exists to scale humanity's access to pasture-based
livestock by building tools that help farmers grow their operations — cattle,
sheep, chickens, any animal raised on grass.

Openpasture is the data and decision layer between what the world knows about
the land and the collars that move the herd. It decides every day whether each
herd should move and where, while keeping the farmer's judgment in the loop.

The durable product is farm operating capability:

- tools that record farm state and produce useful decisions,
- skills that teach an agent how to work through farm jobs,
- curated practitioner knowledge with provenance,
- local-first storage for self-hosted farms,
- hosted infrastructure for farmers who want someone else to run it.

## Product Boundaries

Openpasture has three active repositories with different jobs.

### `openpasture-agent-kit`

The public open-core source of truth. It owns:

- voice, mission, product boundaries, and agent guidance,
- farm domain objects,
- tool definitions and handlers,
- portable skills,
- knowledge ingestion and retrieval,
- local SQLite self-hosting,
- connector surfaces such as CLI, MCP, and Hermes.

If behavior helps any agent operate a pasture-based livestock farm, it belongs
here first.

### `openpasture-cloud`

The hosted revenue product. It owns:

- accounts, auth, tenants, and admin workflows,
- billing and support surfaces,
- managed provisioning and deployment,
- hosted storage and sync,
- proprietary dashboard and hosted UX.

The cloud repo should wrap the agent kit instead of rewriting farm reasoning.

### `openpasture-web`

The closed marketing site. It owns:

- public positioning,
- pricing and lead capture,
- marketing pages,
- links into docs and hosted signup flows.

Marketing copy should stay consistent with the agent kit. It can explain the
promise, but it should not claim that Openpasture runs the farm or moves
animals without the farmer's say. Moves happen within the autonomy the farmer
sets.

## Licensing Posture

Current known repository licenses:

- `openpasture-agent-kit`: AGPL-3.0-only.
- `openpasture-cloud`: all rights reserved.
- `openpasture-web`: no license file found in this workspace.

Do not smooth over licensing conflicts. If a package manifest, README, or site
copy says something different from the license file, flag it and fix the metadata
only when the intended license is clear.

## Agent Rules

Agents working in any Openpasture repo should:

1. Read this file and `SOUL.md` before changing product copy or agent behavior.
2. Preserve the split between OSS agent kit, hosted cloud, and marketing site.
3. Keep self-hosted farm behavior usable without the hosted product.
4. Put runtime-specific glue in connectors, not core farm logic.
5. Use plain language in docs and farmer-facing copy.
6. Treat uncertainty as useful information, not something to hide.
