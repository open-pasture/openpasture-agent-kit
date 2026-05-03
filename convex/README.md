# OpenPasture Convex Backend

This folder is the optional first-party Convex backend for the open agent kit.
SQLite remains the default backend. Use Convex when you want a managed,
reactive store for a hosted or self-hosted OpenPasture runtime.

## What Lives Here

- `schema.ts`: portable farm-state tables.
- `farmStore.ts`: validated Convex functions matching the Python `FarmStore`
  protocol.
- `http.ts`: a small HTTP bridge used by `openpasture.store.convex.ConvexStore`.

This backend intentionally does not include hosted product concerns such as
Clerk accounts, invites, billing, Railway provisioning, support tools, or admin
dashboards. Those belong in `openpasture-cloud`.

## Local Setup

```bash
npm install
npx convex dev
```

Set a runtime key in Convex:

```bash
npx convex env set OPENPASTURE_CONVEX_STORE_KEY "replace-with-a-long-random-secret"
```

Then point an OpenPasture runtime at the Convex HTTP endpoint:

```bash
export OPENPASTURE_STORE=convex
export OPENPASTURE_CONVEX_URL="https://your-deployment.convex.cloud"
export OPENPASTURE_CONVEX_KEY="replace-with-a-long-random-secret"
```

`ConvexStore` normalizes `.convex.cloud` to `.convex.site` when calling the
HTTP bridge.

## OSS Boundary

Convex is optional infrastructure. The open agent kit must keep working with
SQLite and local files. Farm behavior belongs in the Python tools and domain
objects; Convex persists authorized state and provides reactivity for UIs.
