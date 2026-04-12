# Knowledge Productization

`openPasture` needs a clean way to curate, ship, and update ancestral knowledge without mixing it into farmer-specific farm data.

## What Exists Now

The repository already has the key separation points needed for productization:

- `farm.db` holds farmer-specific operational data.
- `knowledge.db` holds shared ancestral knowledge.
- each `KnowledgeEntry` stores structured source provenance
- ingestion batches now persist JSON manifests under `knowledge-batches/`
- the ingestion queue stays separate from the stored knowledge corpus

That means the knowledge base can become a maintained product artifact without changing the farm-data model.

## Publisher Model

Treat the ancestral knowledge base as a curated publisher layer:

- Cody curates practitioner lessons into `knowledge.db`
- each release has a version and a changelog
- farmers receive knowledge updates as a separate artifact from their own farm records
- farmer-specific notes and observations remain in `farm.db`

The practical rule is simple:

- publisher knowledge is replaceable and updatable
- farmer data is local, durable, and never overwritten by a knowledge release

## Recommended Release Unit

The first productizable release unit should be:

- `knowledge.db`
- a release manifest such as `knowledge-release.json`
- optional batch manifests for provenance and auditability

The release manifest should eventually include:

- `version`
- `released_at`
- `entry_count`
- `authors_included`
- `source_count`
- `batch_ids`
- `changelog`
- `min_openpasture_version`

## Update Flow

The clean update path is:

1. Curate new sources into a maintainer knowledge workspace.
2. Run ingestion batches and review the resulting entries.
3. Cut a versioned knowledge release.
4. Ship the release artifact to self-hosted or hosted users.
5. Replace or migrate only the publisher `knowledge.db`.
6. Leave `farm.db` untouched.

This gives a simple mental model for users:

- farm memory is theirs
- ancestral knowledge updates come from the maintainer

## Why Batch Manifests Matter

The new ingestion runner is not just operational plumbing. It creates the provenance needed for a product:

- what source URLs were included
- which author a batch belongs to
- how many lessons were stored
- which sources failed or were skipped
- which entry ids were created

Those manifests can become the raw material for:

- release notes
- QA review
- ingestion audits
- changelog generation
- source attribution in the product

## Hosted Product Path

For a hosted offering, keep the same logical split:

- a maintained shared ancestral knowledge layer
- a farmer-specific operational data layer

The hosted product can distribute the curated knowledge corpus centrally while still letting the same plugin run locally for self-hosted farmers.

## Next Product Steps

The next implementation steps that would make this fully shippable are:

1. Add export and import commands for `knowledge.db` plus a release manifest.
2. Add a release metadata table to the knowledge store.
3. Add an optional overlay model so publisher knowledge and farmer-added knowledge can coexist without conflict.
4. Add signed or checksummed releases so updates are trustworthy.
5. Add changelog generation from batch manifests and source provenance.

## Design Guardrail

Do not turn ancestral knowledge updates into destructive farmer migrations.

The agent should always be able to:

- update the shared knowledge layer
- preserve the farmer's local farm context
- preserve farmer-added observations and custom knowledge
