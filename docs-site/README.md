# OpenPasture Mintlify Docs

This directory contains the public OpenPasture docs site.

It uses Mintlify's current `docs.json` configuration format and adapts source
material from the agent kit docs. The source-of-truth files remain in the repo
root and `docs/`, especially `SOUL.md`, `docs/voice-and-boundaries.md`,
`docs/vision.md`, `docs/architecture.md`, and `docs/cloud-boundary.md`.

## Local Preview

```bash
npx mint@latest dev
```

## Link Check

```bash
npx mint@latest broken-links
```

## Agent Maintenance Flow

Before editing public docs, read `../AGENTS.md` and keep canonical guidance in
the agent kit source files:

- product voice and boundaries: `../SOUL.md` and
  `../docs/voice-and-boundaries.md`
- architecture and repo ownership: `../docs/architecture.md` and
  `../docs/cloud-boundary.md`
- docs-site behavior: this directory's `docs.json` and `.mdx` pages

When a docs change creates durable product guidance, update the source file under
`../docs/` first, then adapt it into the docs site.

## Deployment

Deploy through Mintlify by connecting the repository or using the Mintlify
account flow. That step requires external account access and should not store
tokens or credentials in this repo.

For a GitHub-backed deployment, use the Mintlify dashboard Git Settings flow,
install the Mintlify GitHub App on the docs repository, and set the docs
subdirectory to `docs-site`.
