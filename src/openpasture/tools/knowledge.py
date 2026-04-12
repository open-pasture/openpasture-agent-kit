"""Knowledge storage, queueing, and retrieval tools."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from openpasture.domain import KnowledgeEntry, SourceRecord
from openpasture.knowledge.runner import KnowledgeIngestionRunner
from openpasture.runtime import (
    get_data_dir,
    get_embedder,
    get_ingest_queue_path,
    get_knowledge,
    get_knowledge_store,
)
from openpasture.tools._common import (
    json_response,
    make_id,
    optional_int,
    optional_str,
    optional_str_list,
    require_str,
)

VALID_ENTRY_TYPES = {"principle", "technique", "signal", "mistake"}

STORE_LESSON_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
        "entry_type": {"type": "string"},
        "category": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "author": {"type": "string"},
        "source_url": {"type": "string"},
        "source_title": {"type": "string"},
        "source_kind": {"type": "string"},
        "segment": {"type": "string"},
    },
    "required": ["content", "entry_type", "author", "source_url"],
    "additionalProperties": True,
}

UPDATE_LESSON_SCHEMA = {
    "type": "object",
    "properties": {
        "entry_id": {"type": "string"},
        "content": {"type": "string"},
        "source_url": {"type": "string"},
        "source_title": {"type": "string"},
        "source_kind": {"type": "string"},
        "segment": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "category": {"type": "string"},
    },
    "required": ["entry_id", "content", "source_url"],
    "additionalProperties": True,
}

FIND_SIMILAR_LESSONS_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
        "author": {"type": "string"},
        "limit": {"type": "integer"},
    },
    "required": ["content", "author"],
    "additionalProperties": True,
}

QUEUE_SOURCE_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string"},
        "author": {"type": "string"},
        "source_kind": {"type": "string"},
        "source_title": {"type": "string"},
        "batch_id": {"type": "string"},
    },
    "required": ["url", "author"],
    "additionalProperties": True,
}

PROCESS_QUEUE_SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
    },
    "additionalProperties": True,
}

SEARCH_KNOWLEDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "author": {"type": "string"},
        "entry_type": {"type": "string"},
        "category": {"type": "string"},
        "limit": {"type": "integer"},
    },
    "required": ["query"],
    "additionalProperties": True,
}

LIST_KNOWLEDGE_SOURCES_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": True,
}

CREATE_INGESTION_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "batch_name": {"type": "string"},
        "author": {"type": "string"},
        "source_kind": {"type": "string"},
        "notes": {"type": "string"},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "source_title": {"type": "string"},
                    "source_kind": {"type": "string"},
                },
                "required": ["url"],
                "additionalProperties": True,
            },
        },
    },
    "required": ["batch_name", "author", "sources"],
    "additionalProperties": True,
}

GET_INGESTION_BATCH_STATUS_SCHEMA = {
    "type": "object",
    "properties": {
        "batch_id": {"type": "string"},
    },
    "required": ["batch_id"],
    "additionalProperties": True,
}

CLAIM_INGESTION_BATCH_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "batch_id": {"type": "string"},
    },
    "required": ["batch_id"],
    "additionalProperties": True,
}

RECORD_INGESTION_BATCH_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "batch_id": {"type": "string"},
        "url": {"type": "string"},
        "status": {"type": "string"},
        "stored_count": {"type": "integer"},
        "updated_count": {"type": "integer"},
        "entry_ids": {"type": "array", "items": {"type": "string"}},
        "note": {"type": "string"},
        "error": {"type": "string"},
    },
    "required": ["batch_id", "url", "status"],
    "additionalProperties": True,
}


def _require_entry_type(args: dict[str, object], key: str = "entry_type") -> str:
    entry_type = require_str(args, key)
    if entry_type not in VALID_ENTRY_TYPES:
        raise ValueError(f"'{key}' must be one of {sorted(VALID_ENTRY_TYPES)}.")
    return entry_type


def _build_source_record(args: dict[str, object], *, author: str | None = None) -> SourceRecord:
    source_url = require_str(args, "source_url")
    return SourceRecord(
        source_url=source_url,
        source_title=optional_str(args, "source_title") or source_url,
        source_author=author or require_str(args, "author"),
        source_kind=optional_str(args, "source_kind") or "web",
        segment=optional_str(args, "segment"),
    )


def _dedupe_sources(sources: list[SourceRecord]) -> list[SourceRecord]:
    deduped: list[SourceRecord] = []
    seen: set[tuple[str, str, str, str, str | None]] = set()
    for source in sources:
        key = (
            source.source_url,
            source.source_title,
            source.source_author,
            source.source_kind,
            source.segment,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _queue_path() -> Path:
    path = get_ingest_queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _runner() -> KnowledgeIngestionRunner:
    return KnowledgeIngestionRunner(get_data_dir())


def _require_firecrawl_api_key() -> None:
    if os.environ.get("FIRECRAWL_API_KEY", "").strip():
        return
    raise ValueError(
        "Knowledge ingestion from external web sources requires FIRECRAWL_API_KEY. "
        "Set it before queueing or processing ingestion batches."
    )


def _load_queue() -> list[dict[str, object]]:
    path = _queue_path()
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, list) else []


def _save_queue(items: list[dict[str, object]]) -> None:
    path = _queue_path()
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(items, indent=2, sort_keys=True))
    temp_path.replace(path)


def _pop_batch_queue_item(batch_id: str) -> dict[str, object] | None:
    queue = _load_queue()
    for index, item in enumerate(queue):
        if str(item.get("batch_id", "")).strip() != batch_id:
            continue
        popped = queue.pop(index)
        _save_queue(queue)
        return popped
    return None


def _require_source_payloads(args: dict[str, object]) -> list[dict[str, object]]:
    raw_sources = args.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError("'sources' must be a non-empty list.")
    sources: list[dict[str, object]] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, dict):
            raise ValueError("Each item in 'sources' must be an object.")
        url = str(raw_source.get("url", "")).strip()
        if not url:
            raise ValueError("Each source object must include a non-empty 'url'.")
        sources.append(raw_source)
    return sources


def handle_store_lesson(args: dict[str, object]) -> str:
    """Store one distilled lesson in the ancestral knowledge base."""
    entry = KnowledgeEntry(
        id=make_id("knowledge"),
        farm_id=None,
        entry_type=_require_entry_type(args),
        content=require_str(args, "content"),
        sources=[_build_source_record(args)],
        tags=optional_str_list(args, "tags"),
        category=optional_str(args, "category"),
    )
    embedding_ids = get_embedder().embed([entry])
    if embedding_ids:
        entry.embedding_id = embedding_ids[0]
    get_knowledge_store().store_entries([entry])
    return json_response(status="ok", entry=entry)


def handle_update_lesson(args: dict[str, object]) -> str:
    """Update an existing lesson with consolidated content and new provenance."""
    entry_id = require_str(args, "entry_id")
    existing = get_knowledge_store().get_entry(entry_id)
    if existing is None:
        raise ValueError(f"Knowledge entry '{entry_id}' does not exist.")

    updated_entry = KnowledgeEntry(
        id=existing.id,
        farm_id=existing.farm_id,
        entry_type=existing.entry_type,
        content=require_str(args, "content"),
        sources=_dedupe_sources(
            existing.sources + [_build_source_record(args, author=existing.primary_author or None)]
        ),
        created_at=existing.created_at,
        tags=sorted(set(optional_str_list(args, "tags") or existing.tags)),
        category=optional_str(args, "category") or existing.category,
        embedding_id=existing.embedding_id or existing.id,
    )
    embedding_ids = get_embedder().embed([updated_entry])
    if embedding_ids:
        updated_entry.embedding_id = embedding_ids[0]
    get_knowledge_store().update_entry(updated_entry)
    return json_response(status="ok", entry=updated_entry)


def handle_find_similar_lessons(args: dict[str, object]) -> str:
    """Return nearby lessons for the same author."""
    matches = get_embedder().find_similar(
        content=require_str(args, "content"),
        author=require_str(args, "author"),
        limit=optional_int(args, "limit") or 3,
    )
    return json_response(status="ok", matches=matches)


def handle_queue_source(args: dict[str, object]) -> str:
    """Add a source URL to the ingestion queue if it is not already known."""
    _require_firecrawl_api_key()
    url = require_str(args, "url")
    queue = _load_queue()
    if any(str(item.get("url", "")).strip() == url for item in queue):
        return json_response(status="ok", queued=False, reason="already_queued", url=url)

    known_urls = {source.source_url for source in get_knowledge_store().list_sources()}
    if url in known_urls:
        return json_response(status="ok", queued=False, reason="already_ingested", url=url)

    queue.append(
        {
            "url": url,
            "author": require_str(args, "author"),
            "source_kind": optional_str(args, "source_kind") or "web",
            "source_title": optional_str(args, "source_title"),
            "batch_id": optional_str(args, "batch_id"),
            "queued_at": datetime.utcnow().isoformat(),
        }
    )
    _save_queue(queue)
    return json_response(status="ok", queued=True, size=len(queue), url=url)


def handle_process_queue(args: dict[str, object]) -> str:
    """Pop one or more queued sources for ingestion."""
    _require_firecrawl_api_key()
    count = optional_int(args, "count") or 1
    if count <= 0:
        raise ValueError("'count' must be greater than zero.")

    queue = _load_queue()
    items = queue[:count]
    _save_queue(queue[count:])
    return json_response(status="ok", items=items, count=len(items))


def handle_search_knowledge(args: dict[str, object]) -> str:
    """Retrieve relevant knowledge entries for a planning or ingestion context."""
    query = require_str(args, "query")
    author = optional_str(args, "author")
    category = optional_str(args, "category")
    entry_type = optional_str(args, "entry_type")
    if entry_type and entry_type not in VALID_ENTRY_TYPES:
        raise ValueError(f"'entry_type' must be one of {sorted(VALID_ENTRY_TYPES)}.")
    entries = get_knowledge().search(
        query=query,
        limit=optional_int(args, "limit") or 5,
        authors=[author] if author else None,
        categories=[category] if category else None,
        entry_types=[entry_type] if entry_type else None,
    )
    return json_response(status="ok", query=query, entries=entries)


def handle_list_knowledge_sources(args: dict[str, object]) -> str:
    """List known source records already stored in the knowledge base."""
    del args
    sources = get_knowledge_store().list_sources()
    return json_response(status="ok", count=len(sources), sources=sources)


def handle_create_ingestion_batch(args: dict[str, object]) -> str:
    """Create a reusable ingestion batch and queue its sources."""
    _require_firecrawl_api_key()
    batch = _runner().create_batch(
        batch_name=require_str(args, "batch_name"),
        author=require_str(args, "author"),
        source_kind=optional_str(args, "source_kind") or "web",
        notes=optional_str(args, "notes"),
        sources=_require_source_payloads(args),
    )

    for item in batch["items"]:
        queued = json.loads(
            handle_queue_source(
                {
                    "url": item["url"],
                    "author": batch["author"],
                    "source_kind": item.get("source_kind") or batch["source_kind"],
                    "source_title": item.get("source_title"),
                    "batch_id": batch["id"],
                }
            )
        )
        _runner().mark_item_queued(
            batch["id"],
            url=str(item["url"]),
            reason=None if queued["queued"] else str(queued.get("reason", "skipped")),
        )

    return json_response(status="ok", batch=_runner().get_batch(str(batch["id"])))


def handle_get_ingestion_batch_status(args: dict[str, object]) -> str:
    """Return the current state of one ingestion batch."""
    batch = _runner().get_batch(require_str(args, "batch_id"))
    return json_response(status="ok", batch=batch)


def handle_claim_ingestion_batch_item(args: dict[str, object]) -> str:
    """Claim the next queued item for one ingestion batch."""
    _require_firecrawl_api_key()
    batch_id = require_str(args, "batch_id")
    batch = _runner().get_batch(batch_id)
    item = _pop_batch_queue_item(batch_id)
    recovered = False

    if item is None:
        pending_item = _runner().next_pending_item(batch_id)
        if pending_item is None:
            return json_response(status="ok", count=0, item=None, batch=batch)
        item = {
            "url": pending_item["url"],
            "author": batch["author"],
            "source_kind": pending_item.get("source_kind") or batch["source_kind"],
            "source_title": pending_item.get("source_title"),
            "batch_id": batch_id,
        }
        recovered = True

    claimed = _runner().claim_item(batch_id, url=str(item["url"]))
    return json_response(
        status="ok",
        count=1,
        item=item,
        recovered_from_manifest=recovered,
        batch=_runner().get_batch(batch_id),
        claimed_item=claimed,
    )


def handle_record_ingestion_batch_result(args: dict[str, object]) -> str:
    """Record the outcome for one processed batch item."""
    status = require_str(args, "status")
    if status not in {"completed", "failed", "skipped"}:
        raise ValueError("'status' must be one of ['completed', 'failed', 'skipped'].")

    batch = _runner().record_result(
        require_str(args, "batch_id"),
        url=require_str(args, "url"),
        status=status,
        stored_count=optional_int(args, "stored_count") or 0,
        updated_count=optional_int(args, "updated_count") or 0,
        entry_ids=optional_str_list(args, "entry_ids"),
        note=optional_str(args, "note"),
        error=optional_str(args, "error"),
    )
    return json_response(status="ok", batch=batch)
