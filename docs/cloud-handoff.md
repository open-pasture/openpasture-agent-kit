# Cloud Handoff

This document captures the current alpha baseline so the next repository can
build the hosted OpenPasture layer without re-discovering what was already
validated in the OSS agent.

## Current Baseline

The Hermes-backed OSS agent is working as a self-hosted alpha.

The validated core loop is:

1. onboard the farm
2. store paddocks and herd state
3. record a field observation
4. generate a morning brief
5. return a `MOVE`, `STAY`, or `NEEDS_INFO` recommendation

## What Was Hardened

Recent hardening focused on:

- a preferred composite onboarding flow with `setup_initial_farm`
- one-farm-by-default guardrails
- write-time normalization of field observation source labels
- runtime guidance that distinguishes onboarding from daily operations
- more forgiving live tool behavior for common Hermes/model argument drift
- reusable alpha validation commands and runbooks

## What Was Validated

The current maintainer validation story includes:

- `uv run --python 3.11 openpasture-alpha-validate automated`
- Docker build/runtime validation via `openpasture-alpha-validate docker`
- live Hermes sanity checks using a clean SQLite data directory

The last live handoff sanity pass confirmed:

- one farm created successfully
- two paddocks created successfully
- herd state persisted correctly
- field observations recorded successfully
- a morning brief persisted successfully
- a sensible `MOVE` recommendation returned from the stored state

## OSS Repo Responsibilities

This repo should continue to own:

- the agent runtime and plugin surface
- farm onboarding primitives
- observation storage and normalization
- grazing recommendation logic
- ancestral knowledge logic
- self-hosted scheduling
- self-hosted validation and packaging

## Cloud Repo Responsibilities

The separate cloud repo should own:

- hosted account and tenant management
- hosted storage and backups
- messaging transport setup and orchestration
- billing and subscriptions
- support/admin tooling
- proprietary onboarding UI
- proprietary farm and brief UI surfaces
- managed product analytics and operations

## Residual Quirks To Keep In Mind

The OSS agent is in good shape, but a few live Hermes quirks still exist at the
model-orchestration layer:

- the model can still occasionally probe a tool too early before converging on
  the right payload
- the model can sometimes submit a redundant observation before producing the
  correct brief

These are not core-logic failures, but they are worth tracking as polish work.

## Recommended Next Steps For The Cloud Repo

Start the cloud repo by wrapping the current agent rather than replacing it.

Good first milestones:

- provision a hosted runtime per farm or tenant
- expose a guided onboarding UI over the existing setup flow
- wire a hosted messaging channel
- show current farm state and latest brief in a proprietary UI
- add support/admin tooling for hosted operations

Avoid starting by rewriting the recommendation logic in the cloud layer.

## Reading Order

If you are picking up work later, read these in order:

1. `README.md`
2. `docs/self-hosting.md`
3. `docs/alpha-validation.md`
4. `docs/cloud-boundary.md`
5. `docs/architecture.md`
