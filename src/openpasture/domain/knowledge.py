"""Knowledge primitives backing the ancestral memory system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

KnowledgeType = Literal["principle", "technique", "signal", "mistake"]


@dataclass(slots=True)
class SourceRecord:
    """Source metadata for imported practitioner knowledge."""

    source_url: str
    source_title: str
    source_author: str
    source_kind: str = "youtube"
    segment: str | None = None


@dataclass(slots=True)
class KnowledgeEntry:
    """A structured, retrievable lesson extracted from a trusted source."""

    id: str
    farm_id: str | None
    entry_type: KnowledgeType
    content: str
    sources: list[SourceRecord]
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    embedding_id: str | None = None

    @property
    def primary_source(self) -> SourceRecord | None:
        return self.sources[0] if self.sources else None

    @property
    def primary_author(self) -> str:
        source = self.primary_source
        return source.source_author if source is not None else ""
