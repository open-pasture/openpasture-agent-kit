"""Retrieval interfaces for the ancestral knowledge base."""

from __future__ import annotations

from openpasture.domain import KnowledgeEntry


class KnowledgeRetriever:
    """Selects relevant knowledge for a current farm decision context."""

    def search(self, query: str, farm_id: str | None = None, limit: int = 5) -> list[KnowledgeEntry]:
        raise NotImplementedError("Knowledge retrieval is not implemented yet.")
