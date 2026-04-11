"""Embedding generation for retrievable knowledge entries."""

from __future__ import annotations


class KnowledgeEmbedder:
    """Generates embeddings for structured knowledge entries."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Embedding generation is not implemented yet.")
