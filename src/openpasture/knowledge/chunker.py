"""Lesson extraction for practitioner knowledge sources."""

from __future__ import annotations

from openpasture.domain import KnowledgeEntry


class LessonExtractor:
    """Turns raw transcript text into structured knowledge entries."""

    def extract(self, transcript: str, source_title: str, source_author: str) -> list[KnowledgeEntry]:
        raise NotImplementedError("Lesson extraction is not implemented yet.")
