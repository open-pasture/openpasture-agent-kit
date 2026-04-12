"""Load foundational grazing knowledge into the local knowledge base."""

from __future__ import annotations

from pathlib import Path

from openpasture.domain import KnowledgeEntry
from openpasture.knowledge.chunker import LessonExtractor
from openpasture.knowledge.embedder import KnowledgeEmbedder
from openpasture.store.knowledge_protocol import KnowledgeStore


def _seed_root() -> Path:
    return Path(__file__).resolve().parents[3] / "seed" / "principles"


def load_seed_knowledge(store: KnowledgeStore, embedder: KnowledgeEmbedder) -> list[KnowledgeEntry]:
    extractor = LessonExtractor()
    entries: list[KnowledgeEntry] = []

    for path in sorted(_seed_root().glob("*.md")):
        source_title = path.stem.replace("_", " ").title()
        source_author = source_title
        transcript = path.read_text()
        entries.extend(
            extractor.extract(
                transcript=transcript,
                source_title=source_title,
                source_author=source_author,
                source_url=str(path),
                source_kind="seed",
            )
        )

    if not entries:
        return []

    embedding_ids = embedder.embed(entries)
    for entry, embedding_id in zip(entries, embedding_ids, strict=False):
        entry.embedding_id = embedding_id
    store.store_entries(entries)
    return entries
