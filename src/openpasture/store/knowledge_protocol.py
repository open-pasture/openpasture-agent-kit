"""Storage abstraction for the shared ancestral knowledge base."""

from __future__ import annotations

from typing import Protocol

from openpasture.domain import KnowledgeEntry, SourceRecord


class KnowledgeStore(Protocol):
    """Protocol implemented by knowledge-specific persistence backends."""

    def store_entries(self, entries: list[KnowledgeEntry]) -> list[str]: ...

    def update_entry(self, entry: KnowledgeEntry) -> None: ...

    def get_entry(self, entry_id: str) -> KnowledgeEntry | None: ...

    def search(
        self,
        query: str,
        limit: int = 5,
        entry_types: list[str] | None = None,
        tags: list[str] | None = None,
        authors: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> list[KnowledgeEntry]: ...

    def get_entries_by_author(self, author: str) -> list[KnowledgeEntry]: ...

    def list_sources(self) -> list[SourceRecord]: ...

    def count(self) -> int: ...
