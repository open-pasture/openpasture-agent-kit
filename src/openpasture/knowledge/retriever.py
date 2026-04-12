"""Retrieval interfaces for the ancestral knowledge base."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from openpasture.domain import KnowledgeEntry, SourceRecord
from openpasture.store.protocol import FarmStore


def _tokenize(text: str) -> set[str]:
    return {part.strip(".,:;!?()[]{}").lower() for part in text.split() if part.strip()}


class KnowledgeRetriever:
    """Selects relevant knowledge for a current farm decision context."""

    def __init__(self, persist_dir: str | Path, store: FarmStore | None = None):
        self.persist_dir = Path(persist_dir)
        self.index_path = self.persist_dir / "index.json"
        self.collection_name = "openpasture_knowledge"
        self.store = store

    def _load_index(self) -> dict[str, dict[str, object]]:
        if not self.index_path.exists():
            return {}
        return json.loads(self.index_path.read_text())

    def _entry_from_index(self, payload: dict[str, object]) -> KnowledgeEntry:
        source = payload["source"]
        if not isinstance(source, dict):
            raise ValueError("Knowledge index source payload must be a mapping.")
        return KnowledgeEntry(
            id=str(payload["id"]),
            farm_id=payload.get("farm_id"),
            entry_type=str(payload["entry_type"]),
            content=str(payload["content"]),
            source=SourceRecord(
                source_url=str(source.get("source_url", "")),
                source_title=str(source.get("source_title", "")),
                source_author=str(source.get("source_author", "")),
                source_kind=str(source.get("source_kind", "seed")),
            ),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            tags=[str(tag) for tag in payload.get("tags", [])],
            embedding_id=str(payload.get("embedding_id") or payload["id"]),
        )

    def _fallback_search(self, query: str, farm_id: str | None, limit: int) -> list[KnowledgeEntry]:
        scored: list[tuple[int, KnowledgeEntry]] = []
        query_tokens = _tokenize(query)
        for payload in self._load_index().values():
            entry = self._entry_from_index(payload)
            if farm_id and entry.farm_id not in {None, farm_id}:
                continue
            content_tokens = _tokenize(" ".join([entry.content, *entry.tags, entry.source.source_title]))
            overlap = len(query_tokens & content_tokens)
            if overlap:
                scored.append((overlap, entry))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def search(self, query: str, farm_id: str | None = None, limit: int = 5) -> list[KnowledgeEntry]:
        try:
            import chromadb
        except ImportError:
            chromadb = None

        if chromadb is not None and self.index_path.exists():
            try:
                client = chromadb.PersistentClient(path=str(self.persist_dir))
                collection = client.get_or_create_collection(name=self.collection_name)
                where = None
                if farm_id:
                    where = {"farm_id": farm_id}
                result = collection.query(query_texts=[query], n_results=limit, where=where)
                ids = result.get("ids", [[]])[0]
                index = self._load_index()
                entries = [self._entry_from_index(index[item_id]) for item_id in ids if item_id in index]
                if entries:
                    return entries
            except Exception:
                pass

        entries = self._fallback_search(query, farm_id, limit)
        if entries:
            return entries

        if self.store is None:
            return []
        return self.store.search_knowledge(query=query, farm_id=farm_id, limit=limit)
