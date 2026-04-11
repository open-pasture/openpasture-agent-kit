"""Knowledge ingestion and retrieval tools."""

from __future__ import annotations

import json


def _stub(name: str, **payload: object) -> str:
    return json.dumps({"status": "stub", "tool": name, **payload})


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
    return _stub("ingest_youtube", args=args)


def handle_search_knowledge(args: dict[str, object]) -> str:
    """Retrieve relevant knowledge entries for the current planning context."""
    return _stub("search_knowledge", args=args)
