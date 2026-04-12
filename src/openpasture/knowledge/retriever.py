"""Retrieval interfaces for the ancestral knowledge base."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from openpasture.domain import KnowledgeEntry, SourceRecord
from openpasture.store.knowledge_protocol import KnowledgeStore


def _tokenize(text: str) -> set[str]:
    return {part.strip(".,:;!?()[]{}").lower() for part in text.split() if part.strip()}


class KnowledgeRetriever:
    """Selects relevant knowledge for a current farm decision context."""

    def __init__(self, persist_dir: str | Path, store: KnowledgeStore | None = None):
        self.persist_dir = Path(persist_dir)
        self.index_path = self.persist_dir / "index.json"
        self.collection_name = "openpasture_knowledge"
        self.store = store

    def _load_index(self) -> dict[str, dict[str, object]]:
        if not self.index_path.exists():
            return {}
        return json.loads(self.index_path.read_text())

    def _entry_from_index(self, payload: dict[str, object]) -> KnowledgeEntry:
        raw_sources = payload.get("sources", [])
        if not isinstance(raw_sources, list):
            raise ValueError("Knowledge index sources payload must be a list.")
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

    def _matches_filters(
        self,
        entry: KnowledgeEntry,
        *,
        authors: list[str] | None = None,
        categories: list[str] | None = None,
        entry_types: list[str] | None = None,
    ) -> bool:
        if authors and entry.primary_author not in set(authors):
            return False
        if categories and entry.category not in set(categories):
            return False
        if entry_types and entry.entry_type not in set(entry_types):
            return False
        return True

    def _fallback_search(
        self,
        query: str,
        farm_id: str | None,
        limit: int,
        *,
        authors: list[str] | None = None,
        categories: list[str] | None = None,
        entry_types: list[str] | None = None,
    ) -> list[KnowledgeEntry]:
        scored: list[tuple[int, KnowledgeEntry]] = []
        query_tokens = _tokenize(query)
        for payload in self._load_index().values():
            entry = self._entry_from_index(payload)
            if farm_id and entry.farm_id not in {None, farm_id}:
                continue
            if not self._matches_filters(
                entry,
                authors=authors,
                categories=categories,
                entry_types=entry_types,
            ):
                continue
            content_tokens = _tokenize(
                " ".join(
                    [
                        entry.content,
                        *entry.tags,
                        entry.category or "",
                        entry.primary_source.source_title if entry.primary_source else "",
                    ]
                )
            )
            overlap = len(query_tokens & content_tokens)
            if overlap:
                scored.append((overlap, entry))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def search(
        self,
        query: str,
        farm_id: str | None = None,
        limit: int = 5,
        *,
        authors: list[str] | None = None,
        categories: list[str] | None = None,
        entry_types: list[str] | None = None,
    ) -> list[KnowledgeEntry]:
        try:
            import chromadb
        except ImportError:
            chromadb = None

        if chromadb is not None and self.index_path.exists():
            try:
                client = chromadb.PersistentClient(path=str(self.persist_dir))
                collection = client.get_or_create_collection(name=self.collection_name)
                result = collection.query(query_texts=[query], n_results=max(limit * 5, limit))
                ids = result.get("ids", [[]])[0]
                index = self._load_index()
                entries = [
                    self._entry_from_index(index[item_id])
                    for item_id in ids
                    if item_id in index
                ]
                filtered = [
                    entry
                    for entry in entries
                    if (not farm_id or entry.farm_id in {None, farm_id})
                    and self._matches_filters(
                        entry,
                        authors=authors,
                        categories=categories,
                        entry_types=entry_types,
                    )
                ]
                entries = filtered[:limit]
                if entries:
                    return entries
            except Exception:
                pass

        entries = self._fallback_search(
            query,
            farm_id,
            limit,
            authors=authors,
            categories=categories,
            entry_types=entry_types,
        )
        if entries:
            return entries

        if self.store is None:
            return []
        return self.store.search(
            query=query,
            limit=limit,
            authors=authors,
            categories=categories,
            entry_types=entry_types,
        )
