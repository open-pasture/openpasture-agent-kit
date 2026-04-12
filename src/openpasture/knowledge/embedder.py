"""Embedding generation for retrievable knowledge entries."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from openpasture.domain import KnowledgeEntry


class KnowledgeEmbedder:
    """Persists semantic-search data for structured knowledge entries."""

    def __init__(self, persist_dir: str | Path):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.persist_dir / "index.json"
        self.collection_name = "openpasture_knowledge"

    def _load_index(self) -> dict[str, dict[str, object]]:
        if not self.index_path.exists():
            return {}
        return json.loads(self.index_path.read_text())

    def _save_index(self, index: dict[str, dict[str, object]]) -> None:
        self.index_path.write_text(json.dumps(index, indent=2, sort_keys=True))

    def _serialize_entry(self, entry: KnowledgeEntry) -> dict[str, object]:
        return {
            "id": entry.id,
            "farm_id": entry.farm_id,
            "entry_type": entry.entry_type,
            "content": entry.content,
            "source": asdict(entry.source),
            "created_at": entry.created_at.isoformat(),
            "tags": entry.tags,
            "embedding_id": entry.embedding_id,
        }

    def _upsert_fallback_index(self, entries: list[KnowledgeEntry]) -> list[str]:
        index = self._load_index()
        ids: list[str] = []
        for entry in entries:
            embedding_id = entry.embedding_id or entry.id
            entry.embedding_id = embedding_id
            index[embedding_id] = self._serialize_entry(entry)
            ids.append(embedding_id)
        self._save_index(index)
        return ids

    def embed(self, entries: list[KnowledgeEntry]) -> list[str]:
        """Store retrievable knowledge, preferring ChromaDB when available."""
        ids = self._upsert_fallback_index(entries)

        try:
            import chromadb
        except ImportError:
            return ids

        try:
            client = chromadb.PersistentClient(path=str(self.persist_dir))
            collection = client.get_or_create_collection(name=self.collection_name)
            collection.upsert(
                ids=ids,
                documents=[entry.content for entry in entries],
                metadatas=[
                    {
                        "farm_id": entry.farm_id or "",
                        "entry_type": entry.entry_type,
                        "source_title": entry.source.source_title,
                        "source_author": entry.source.source_author,
                        "tags": ",".join(entry.tags),
                    }
                    for entry in entries
                ],
            )
        except Exception:
            # The JSON fallback keeps retrieval working even when ChromaDB is not available
            # or cannot initialize models in a constrained self-hosted environment.
            return ids

        return ids
