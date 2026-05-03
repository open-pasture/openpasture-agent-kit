# First-Party Convex Backend

Convex is a first-party OpenPasture backend, not the OpenPasture core. The core
farm behavior, tools, skills, and domain objects remain in this agent kit. SQLite
stays the default local and OSS backend. Convex is available for:

- the hosted OpenPasture product,
- self-hosted farmers who want a managed real-time data plane,
- future dashboards and companion UIs that need reactive farm state.

The hosted product can use Convex as the primary store without making Convex a
requirement for the open agent kit.

## Target Split

- Local and self-hosted users keep `OPENPASTURE_STORE=sqlite`.
- Self-hosted users may opt into `OPENPASTURE_STORE=convex`.
- Hosted MCP runs `OPENPASTURE_STORE=convex` for new tenants once the backend is
  ready.
- The hosted web app uses Convex directly for product state and real-time GIS
  updates.
- MCP, CLI, and future hosted surfaces continue to share the same `FarmStore`
  protocol boundary.
- Cloud-only account, billing, invite, provisioning, and support workflows stay
  in `openpasture-cloud`.

## OSS Convex Data Model

The OSS Convex backend owns portable farm state only:

- `farms`
- `landUnits`
- `paddocks`
- `herds`
- `observations`
- `data_pipelines`
- `farmer_actions`
- `movement_decisions`
- `daily_briefs`

Each table includes a `tenantKey` so a self-hosted Convex deployment can remain
single-tenant by convention, while the hosted product can map its per-tenant
runtime key into the same store contract.

Indexes should match the access patterns used by the `FarmStore` protocol:

- `by_tenant_key`
- `by_tenant_key_and_farm_id`
- status/date-specific indexes for pending actions, observations, and plans

## Hosted Cloud Extensions

`openpasture-cloud` may extend the OSS farm backend with hosted-only tables:

- `tenants`
- `invites`
- `apiKeys`
- `pendingCommands`
- Railway provisioning metadata
- admin and support views
- Clerk auth integration

Those tables are not part of the portable farm backend. They are product
infrastructure for the hosted service.

## Function Shape

- Validate args on every Convex query and mutation.
- Scope every read and write by the authenticated runtime key / resolved tenant.
- Keep public HTTP entry points thin and route to validated query/mutation
  functions.
- Do not duplicate grazing logic in Convex functions. Convex persists and
  authorizes; agent-kit tools decide farm behavior.

## Python Store

`src/openpasture/store/convex.py` implements the same `FarmStore` protocol as
SQLite:

- Translate domain objects to Convex document payloads.
- Preserve the same method names and return shapes as `SQLiteStore`.
- Keep tool handlers unchanged.
- Use environment configuration already present in `OpenPastureConfig`:
  `OPENPASTURE_CONVEX_URL` and `OPENPASTURE_CONVEX_KEY`.
- Normalize `.convex.cloud` deployment URLs to `.convex.site` for HTTP store
  calls.

## Knowledge Storage

The pilot can keep tenant knowledge local per Railway volume. For larger hosted
rollouts, store knowledge metadata in Convex and move embeddings/vector search
to a managed vector backend if Chroma-on-Railway becomes the bottleneck.

## Migration Posture

Existing hosted tenants can keep the SQLite plus sync-daemon path until their
state is backfilled into Convex. New hosted tenants should be able to start
directly on `OPENPASTURE_STORE=convex`.

The command queue remains useful for long-running jobs and runtime-only work,
but routine farm state writes should go through `ConvexStore` once the hosted
runtime uses Convex as its primary store.
