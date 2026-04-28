# Hosted Convex Roadmap

The first hosted MCP rollout uses SQLite and Chroma on a Railway persistent
volume, with one hashed tenant directory per manually configured API key. This
keeps the 5-farmer pilot close to the already implemented local backend.

For the 50-farmer hosted rollout, move hosted farm state to Convex while keeping
SQLite as the default OSS and local backend.

## Target Split

- Local and self-hosted users keep `OPENPASTURE_STORE=sqlite`.
- Hosted MCP runs `OPENPASTURE_STORE=convex`.
- The future hosted web app uses Convex directly for product state.
- MCP, CLI, and future hosted surfaces continue to share the same `FarmStore`
  protocol boundary.

## Convex Data Model

Add Convex tables for:

- `tenants`
- `farms`
- `paddocks`
- `herds`
- `observations`
- `data_pipelines`
- `farmer_actions`
- `movement_decisions`
- `daily_briefs`

Each tenant-owned table should include `tenant_id` and indexes for the access
patterns used by the `FarmStore` protocol, such as:

- `by_tenant_id`
- `by_tenant_id_and_farm_id`
- status/date-specific indexes for pending actions, observations, and plans

## Function Shape

- Validate args on every Convex query and mutation.
- Scope every read and write by `tenant_id`.
- Keep public functions minimal; prefer internal functions where the hosted MCP
  server is the only caller.
- Do not accept arbitrary user ids from clients. The hosted MCP server validates
  its URL API key and resolves the tenant before calling Convex.

## Python Store

Replace the placeholder `ConvexStore` with a real `FarmStore` implementation:

- Translate domain objects to Convex document payloads.
- Preserve the same method names and return shapes as `SQLiteStore`.
- Keep tool handlers unchanged.
- Use environment configuration already present in `OpenPastureConfig`:
  `OPENPASTURE_CONVEX_URL` and `OPENPASTURE_CONVEX_KEY`.

## Knowledge Storage

The pilot can keep tenant knowledge local per Railway volume. For larger hosted
rollouts, store knowledge metadata in Convex and move embeddings/vector search
to a managed vector backend if Chroma-on-Railway becomes the bottleneck.
