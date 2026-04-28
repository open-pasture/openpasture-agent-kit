---
name: data-pipeline-setup
description: Set up a farm data pipeline for an external service using Firecrawl browser profiles, farmer-assisted login, site exploration, and generated vendor skills. Use when a farmer asks to connect a service like NoFence or to create a recurring data pipeline.
version: 1.0.0
---
# Data Pipeline Setup

## When to Use

Use this skill when a farmer wants the agent to connect a web-based farm system and turn it into a recurring observation pipeline.

Examples:

- "Set up a data pipeline with NoFence."
- "Connect Gallagher so you can pull alerts."
- "Use my grazing app as a daily data source."

## Core Rule

Use Firecrawl CLI directly for the live setup. Do not bounce through bespoke setup tools for login handoff, exploration, or "continue" steps.

The only plugin tool this setup should need is `save_data_pipeline` once the agent already knows:

- the vendor,
- the login URL,
- the profile ID,
- the target URLs to revisit,
- the extraction prompts,
- the reusable navigation notes,
- the observation mapping and schedule.

Then use `run_data_pipeline` for verification and `list_data_pipelines` for inspection.

## Architecture Guardrails

1. Keep farm-specific state in a `DataPipeline` record, not in the generated vendor skill.
2. Keep reusable navigation knowledge in `skills/pipeline-{vendor}/SKILL.md`.
3. Never store passwords, session cookies, or raw secrets in the repo.
4. In OSS, generated vendor skills stay local unless the farmer explicitly submits them for review.
5. In cloud deployments, generated vendor skills should remain reviewable artifacts. Preserve enough structure that an automated review pipeline can diff and promote them later.

## Live Setup Procedure

### Phase 1: Provision

1. Confirm the vendor name and login URL.
2. Resolve the active `farm_id`.
3. Derive a profile name like `{vendor_slug}-{farm_id}`.
4. Use Firecrawl CLI yourself to start the session, for example:

```sh
firecrawl scrape "https://example.com/login" --profile "{vendor_slug}-{farm_id}" --json
```

5. Capture the returned `scrapeId`.
6. Open the interactive handoff from the same scrape session, for example:

```sh
firecrawl interact --scrape-id "<scrape-id>" --prompt "Do not change the page. Just say ready for login handoff." --json
```

7. Give the farmer the returned live view URL.
8. Wait for explicit confirmation before continuing.

Important:

- Keep working against the same Firecrawl session after the farmer says they are logged in.
- Do not tear down the session and start over unless the session is actually gone or the saved profile truly failed to persist.

### Phase 2: Explore

1. After the farmer says they are logged in, inspect the same active session first.
2. Ask Firecrawl to report whether the current page is authenticated before assuming anything.
3. If authenticated, continue exploring from that same `scrapeId`.
4. Scrape first, then use interact only when navigation or clicks are required.
5. Inspect the authenticated site to identify:
   - the key data pages,
   - the useful entities and fields,
   - the URLs that should be revisited on cron runs,
   - any filters, tabs, pagination, or gotchas.
6. Summarize what data seems available before assuming it is useful.

If `skills/pipeline-{vendor}/SKILL.md` already exists, use it as the starting point and only re-explore when the site appears to have changed.

### Phase 3: Converse

1. Tell the farmer what data the agent found in plain language.
2. Ask which signals matter for the morning brief and how often they should be collected.
3. Confirm the intended cadence. Default to daily unless the data is unusually time-sensitive or static.
4. Confirm the observation mapping before enabling anything.

Only collect data the farmer understands and wants.

### Phase 4: Persist

Once the site is understood, call `save_data_pipeline` with the learned configuration.

The saved pipeline should include:

- vendor name,
- Firecrawl profile ID,
- login URL,
- target URLs,
- extraction prompts,
- observation source and tags,
- schedule,
- reusable login and navigation notes,
- generated vendor skill hash.

Keep the generated skill reusable across farms. Do not bake in farm IDs, raw account-specific secrets, or farmer-specific preferences that belong in the store.

### Phase 5: Verify

1. Run one test collection with `run_data_pipeline` before enabling the cron.
2. Show the farmer a sample of the resulting observation.
3. Ask whether the collected signal is actually useful.
4. Only enable the recurring run after the farmer confirms it looks right.

## Generated Vendor Skill Template

Use this structure for `skills/pipeline-{vendor}/SKILL.md`:

```markdown
---
name: pipeline-{vendor}
description: Collect recurring farm observations from {Vendor} using an authenticated Firecrawl profile and the learned site navigation.
version: 1.0.0
---
# Pipeline {Vendor}

## Login

- Login URL: `https://...`
- Expected authentication flow: `...`

## Navigation

- Start page: `...`
- Key pages:
  - `...`
  - `...`

## Extraction Prompts

- `...`
- `...`

## Output Shape

- Return JSON objects with:
  - `observed_at`
  - `content`
  - `metrics`
  - optional `tags`, `paddock_id`, `herd_id`, `media_url`

## Gotchas

- `...`
```

## Pitfalls

- Do not pretend a login succeeded if the farmer has not confirmed it.
- Do not throw away the active live session just because the user said "done".
- Do not store secrets in the generated skill.
- Do not collect every visible metric just because it exists.
- Do not create a farm-specific vendor skill when a reusable one will do.
- Do not enable cron collection before a successful sample run.
