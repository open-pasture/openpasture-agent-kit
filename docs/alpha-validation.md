# Alpha Validation

This runbook is for maintainers validating the `openPasture` agent kit after a Hermes connector update or compatibility change.

For the broader architectural split and the current cloud handoff notes, also
read [`cloud-boundary.md`](cloud-boundary.md) and
[`cloud-handoff.md`](cloud-handoff.md).

## Supported Hermes Target

The current validated Hermes target is:

- version: `0.8.0`
- commit: `1cec910b6a064d4e4821930be5cfaaf6145a2afd`

Check the pinned target from the repo itself:

```bash
uv run --python 3.11 openpasture-alpha-validate show-target
```

If you want to move to a newer Hermes build, pin that new commit in `pyproject.toml`, rerun this full validation flow, and only then bless the update.

## Automated OSS Alpha Checks

Run the named OSS alpha suite:

```bash
uv run --python 3.11 openpasture-alpha-validate automated
```

That command runs the `pytest -m alpha` subset, which covers:

- Hermes connector registration and tool-calling compatibility
- the farm-to-brief public tool flow
- scheduled morning brief persistence and delivery injection
- first-run seed loading
- runtime notices and knowledge-tool behavior
- validation harness helpers

If you want the full suite instead of the named alpha subset:

```bash
uv run --python 3.11 pytest
```

## Docker Build And Boot Check

Make sure Docker Desktop or the Docker daemon is running, then run:

```bash
uv run --python 3.11 openpasture-alpha-validate docker
```

This does two things:

- builds the repo image from `Dockerfile`
- starts one short-lived container and asserts that runtime initialization succeeds and seed knowledge loads

## Two-Profile Pilot Setup On One Machine

Use Hermes profiles instead of two separate machines for local pilot validation.

Recommended profile names:

- `alpha`
- `beta`

Create them from your known-good active profile:

```bash
uv run --python 3.11 hermes profile create alpha --clone
uv run --python 3.11 hermes profile create beta --clone
```

Inspect the profile-local `.env` path for each profile:

```bash
uv run --python 3.11 hermes -p alpha config env-path
uv run --python 3.11 hermes -p beta config env-path
```

Set these variables in each profile's `.env` file:

For `alpha`:

```bash
OPENPASTURE_STORE=sqlite
OPENPASTURE_DATA_DIR=/absolute/path/to/.openpasture-alpha
OPENPASTURE_BRIEF_TIME=06:00
```

For `beta`:

```bash
OPENPASTURE_STORE=sqlite
OPENPASTURE_DATA_DIR=/absolute/path/to/.openpasture-beta
OPENPASTURE_BRIEF_TIME=06:00
```

Guidelines:

- use absolute paths for `OPENPASTURE_DATA_DIR`
- keep `OPENPASTURE_STORE=sqlite`
- use separate messaging credentials if both profiles will run gateways at the same time

Check the profile state before testing:

```bash
uv run --python 3.11 hermes -p alpha status --all
uv run --python 3.11 hermes -p beta status --all
```

## Messaging Auth And Real Conversation Check

Configure messaging for each profile:

```bash
uv run --python 3.11 hermes -p alpha gateway setup
uv run --python 3.11 hermes -p beta gateway setup
```

Run one real conversation per profile:

```bash
uv run --python 3.11 hermes -p alpha chat -t openpasture
uv run --python 3.11 hermes -p beta chat -t openpasture
```

Use the same prompts for both profiles:

1. Onboard a farm:

```text
I am setting up a new pasture-based livestock farm. Help me create the farm, paddocks, and first herd.
```

2. Add one real field note:

```text
Record this observation for the current paddock: forage is getting short and muddy near the water point.
```

3. Ask for the brief:

```text
Give me today's morning brief.
```

Confirm manually that each profile:

- authenticates successfully through the configured messaging surface
- creates an isolated farm without leaking data across profiles
- accepts the field note as a usable observation
- returns a sensible `MOVE`, `STAY`, or `NEEDS_INFO` brief with reasoning

## Scheduled Brief Delivery Check

For each profile, set `OPENPASTURE_BRIEF_TIME` to a minute or two in the future, keep the live session open, and wait for the scheduled brief injection.

Recommended flow for `alpha` and then `beta`:

1. Edit the profile `.env` file so `OPENPASTURE_BRIEF_TIME` is a near-future local time.
2. Start a live session:

```bash
uv run --python 3.11 hermes -p alpha chat -t openpasture
```

3. Leave the session open past the scheduled time.
4. Confirm the scheduled morning brief is injected into that live Hermes session.

If delivery fails, inspect:

```bash
uv run --python 3.11 hermes -p alpha gateway status --deep
uv run --python 3.11 hermes -p alpha logs --component gateway --since 15m
uv run --python 3.11 hermes -p alpha logs --component agent --since 15m
```

Repeat the same check for `beta`.

## Backup And Restore Validation

There are two layers worth checking.

Hermes profile backup:

```bash
uv run --python 3.11 hermes -p alpha profile export alpha -o artifacts/alpha-profile.tar.gz
uv run --python 3.11 hermes -p beta profile export beta -o artifacts/beta-profile.tar.gz
```

SQLite data backup and restore verification:

```bash
uv run --python 3.11 openpasture-alpha-validate sqlite-backup-restore \
  --data-dir /absolute/path/to/.openpasture-alpha \
  --work-dir artifacts/alpha-sqlite-restore-check

uv run --python 3.11 openpasture-alpha-validate sqlite-backup-restore \
  --data-dir /absolute/path/to/.openpasture-beta \
  --work-dir artifacts/beta-sqlite-restore-check
```

That command:

- verifies `farm.db` and `knowledge.db` exist
- runs SQLite integrity checks
- creates a compressed backup archive
- restores it into a temp location
- verifies the restored databases are readable

## Suggested Validation Cadence

Run this full flow when:

- Hermes is repinned forward
- plugin registration or runtime integration changes
- scheduling or storage changes
- Docker/runtime packaging changes

Minimum repeatable check after small plugin changes:

1. `uv run --python 3.11 openpasture-alpha-validate automated`
2. `uv run --python 3.11 openpasture-alpha-validate docker`

Full pilot revalidation after Hermes updates:

1. automated suite
2. Docker check
3. `alpha` conversation
4. `beta` conversation
5. scheduled brief test on both profiles
6. backup/restore check on both profiles
