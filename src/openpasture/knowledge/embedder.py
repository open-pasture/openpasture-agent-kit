"""Embedding generation for retrievable knowledge entries."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from openpasture.domain import KnowledgeEntry, SourceRecord


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
            "category": entry.category,
            "content": entry.content,
            "sources": [
                {
                    "source_url": source.source_url,
                    "source_title": source.source_title,
                    "source_author": source.source_author,
                    "source_kind": source.source_kind,
                    "segment": source.segment,
                }
                for source in entry.sources
            ],
            "created_at": entry.created_at.isoformat(),
            "tags": entry.tags,
            "embedding_id": entry.embedding_id,
        }

    def _entry_from_payload(self, payload: dict[str, object]) -> KnowledgeEntry:
        raw_sources = payload.get("sources", [])
        if not isinstance(raw_sources, list):
            raw_sources = []
        return KnowledgeEntry(
            id=str(payload["id"]),
            farm_id=payload.get("farm_id"),
            entry_type=str(payload["entry_type"]),
            category=str(payload["category"]) if payload.get("category") is not None else None,
            content=str(payload["content"]),
            sources=[
                SourceRecord(
                    source_url=str(source.get("source_url", "")),
                    source_title=str(source.get("source_title", "")),
                    source_author=str(source.get("source_author", "")),
                    source_kind=str(source.get("source_kind", "seed")),
                    segment=str(source["segment"]) if source.get("segment") is not None else None,
                )
                for source in raw_sources
                if isinstance(source, dict)
            ],
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            tags=[str(tag) for tag in payload.get("tags", [])],
            embedding_id=str(payload.get("embedding_id") or payload["id"]),
        )

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
                        "category": entry.category or "",
                        "source_title": entry.primary_source.source_title if entry.primary_source else "",
                        "source_author": entry.primary_author,
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

    def find_similar(
        self,
        content: str,
        author: str,
        limit: int = 3,
    ) -> list[dict[str, object]]:
        """Find similar entries, preferring ChromaDB when available."""
        index = self._load_index()

        try:
            import chromadb
        except ImportError:
            chromadb = None

        if chromadb is not None and index:
            try:
                client = chromadb.PersistentClient(path=str(self.persist_dir))
                collection = client.get_or_create_collection(name=self.collection_name)
                result = collection.query(
                    query_texts=[content],
                    n_results=limit,
                    where={"source_author": author},
                )
                ids = result.get("ids", [[]])[0]
                distances = result.get("distances", [[]])[0]
                matches: list[dict[str, object]] = []
                for item_id, distance in zip(ids, distances, strict=False):
                    payload = index.get(item_id)
                    if payload is None:
                        continue
                    similarity = max(0.0, 1.0 - float(distance))
                    matches.append(
                        {
                            "entry": self._entry_from_payload(payload),
                            "similarity": round(similarity, 4),
                        }
                    )
                if matches:
                    return matches
            except Exception:
                pass

        query_tokens = {token.lower() for token in content.split() if token.strip()}
        scored: list[dict[str, object]] = []
        for payload in index.values():
            entry = self._entry_from_payload(payload)
            if entry.primary_author != author:
                continue
            entry_tokens = {token.lower() for token in " ".join([entry.content, *entry.tags]).split() if token.strip()}
            overlap = len(query_tokens & entry_tokens)
            if not overlap:
                continue
            similarity = overlap / max(len(query_tokens), 1)
            scored.append({"entry": entry, "similarity": round(similarity, 4)})

        scored.sort(key=lambda item: float(item["similarity"]), reverse=True)
        return scored[:limit]
