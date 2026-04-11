# Knowledge Base

The knowledge base is the agent's durable ancestral memory.

## Purpose

`openPasture` should not rely only on generic model priors. It should reason with curated lessons from trusted practitioners and connect those lessons to the daily condition of a specific farm.

## Source Types

The first ingestion focus is YouTube transcripts from trusted rotational and regenerative grazing practitioners.

Examples of source categories:

- rotational grazing instruction,
- daily movement practices,
- animal behavior signals,
- multi-species sequencing,
- pasture observation heuristics,
- technology-assisted pasture systems.

## Extraction Model

Every source should be distilled into one or more `KnowledgeEntry` objects.

The initial types are:

- `principle`: a durable rule of thumb,
- `technique`: a repeatable management move,
- `signal`: something observable that changes interpretation,
- `mistake`: a known anti-pattern or warning sign.

## Pipeline

```mermaid
flowchart LR
    Source[SourceURL] --> Transcript[TranscriptAcquisition]
    Transcript --> Extraction[LessonExtraction]
    Extraction --> Embedding[EmbeddingGeneration]
    Embedding --> Storage[KnowledgeStorage]
    Storage --> Retrieval[RetrievalAtPlanTime]
```

## Retrieval During Planning

When the agent evaluates a movement decision, it should retrieve the most relevant knowledge entries for the current farm context rather than loading the entire corpus blindly.

The result should ground recommendations in explicit lessons and make the reasoning legible.

## Seed Knowledge

The repository includes starter knowledge based on cross-cutting principles and named practitioners. This seed exists to make the first local test useful before a farmer adds their own sources.
