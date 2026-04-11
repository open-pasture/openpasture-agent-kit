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


@dataclass(slots=True)
class KnowledgeEntry:
    """A structured, retrievable lesson extracted from a trusted source."""

    id: str
    farm_id: str | None
    entry_type: KnowledgeType
    content: str
    source: SourceRecord
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)
    embedding_id: str | None = None
