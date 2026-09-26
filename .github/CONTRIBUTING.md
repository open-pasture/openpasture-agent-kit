# Contributing

Thanks for contributing to `Openpasture`.

## What Matters Most

- Keep the agent core self-hostable.
- Preserve clean domain primitives.
- Avoid pulling behavior into hosted infrastructure unless self-hosting would remain intact.
- Prefer small, explicit modules over clever indirection.
- Write docs when you add concepts.

## Development Expectations

- Start from `docs/vision.md`, `docs/architecture.md`, and `docs/contracts.md`.
- Review `docs/cloud-boundary.md` before introducing hosted-only concepts.
- Review `docs/cloud-handoff.md` for the current alpha baseline and the known handoff assumptions.
- Keep new capabilities aligned with the daily decision cycle, and keep every decision's inputs and outcome on the record.
- Add tests where contracts or domain rules become non-trivial.
- Keep language farmer-readable.

## Validation

Run the reusable alpha validation path before opening a pull request:

```bash
uv run --python 3.11 openpasture-alpha-validate automated
```

For packaging or runtime changes, also run:

```bash
uv run --python 3.11 openpasture-alpha-validate docker
```

The full maintainer validation runbook lives in `docs/alpha-validation.md`.

## Scope Discipline

This repository is the open-source engine. Hosted provisioning, billing, notifications, and the farm view belong in `openpasture-cloud` unless the same behavior must exist for self-hosted farmers too. Collar firmware and the collar protocol belong in `opencollar`.
