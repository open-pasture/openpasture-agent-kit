"""Knowledge ingestion and retrieval tools."""

from __future__ import annotations

from openpasture.knowledge.chunker import LessonExtractor
from openpasture.knowledge.youtube import YouTubeTranscriptFetcher
from openpasture.runtime import get_embedder, get_knowledge, get_store
from openpasture.tools._common import json_response, optional_int, optional_str, require_str


INGEST_YOUTUBE_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string"},
        "farm_id": {"type": "string"},
    },
    "required": ["url"],
    "additionalProperties": True,
}

SEARCH_KNOWLEDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "farm_id": {"type": "string"},
        "limit": {"type": "integer"},
    },
    "required": ["query"],
    "additionalProperties": True,
}


def handle_ingest_youtube(args: dict[str, object]) -> str:
    """Ingest a YouTube transcript into the knowledge base."""
    url = require_str(args, "url")
    farm_id = optional_str(args, "farm_id")
    payload = YouTubeTranscriptFetcher().fetch(url)
    entries = LessonExtractor().extract(
        transcript=str(payload["transcript"]),
        source_title=str(payload["title"]),
        source_author=str(payload["author"]),
        source_url=url,
        source_kind="youtube",
    )
    if farm_id:
        for entry in entries:
            entry.farm_id = farm_id
    embedding_ids = get_embedder().embed(entries)
    for entry, embedding_id in zip(entries, embedding_ids, strict=False):
        entry.embedding_id = embedding_id
    get_store().store_knowledge(entries)
    return json_response(status="ok", source=payload, entries=entries)


def handle_search_knowledge(args: dict[str, object]) -> str:
    """Retrieve relevant knowledge entries for the current planning context."""
    query = require_str(args, "query")
    entries = get_knowledge().search(
        query=query,
        farm_id=optional_str(args, "farm_id"),
        limit=optional_int(args, "limit") or 5,
    )
    return json_response(status="ok", query=query, entries=entries)
