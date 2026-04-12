from __future__ import annotations

import json

import pytest

from openpasture.runtime import initialize
from openpasture.tools.knowledge import (
    handle_claim_ingestion_batch_item,
    handle_create_ingestion_batch,
    handle_find_similar_lessons,
    handle_get_ingestion_batch_status,
    handle_list_knowledge_sources,
    handle_process_queue,
    handle_queue_source,
    handle_record_ingestion_batch_result,
    handle_search_knowledge,
    handle_store_lesson,
    handle_update_lesson,
)

pytestmark = pytest.mark.alpha


def test_store_update_and_search_knowledge_tools():
    initialize()

    stored = json.loads(
        handle_store_lesson(
            {
                "content": "Back fencing protects fresh regrowth from immediate re-bite.",
                "entry_type": "principle",
                "category": "grazing-management",
                "tags": ["back-fencing", "recovery"],
                "author": "Greg Judy",
                "source_url": "https://example.com/video-a",
                "source_title": "Back Fencing Basics",
                "source_kind": "youtube",
                "segment": "04:10",
            }
        )
    )
    entry_id = stored["entry"]["id"]

    similar = json.loads(
        handle_find_similar_lessons(
            {
                "content": "Back fencing protects fresh regrowth and speeds recovery.",
                "author": "Greg Judy",
            }
        )
    )
    assert similar["matches"]
    assert similar["matches"][0]["entry"]["id"] == entry_id

    updated = json.loads(
        handle_update_lesson(
            {
                "entry_id": entry_id,
                "content": "Back fencing protects fresh regrowth from immediate re-bite and keeps recovery cleaner.",
                "source_url": "https://example.com/video-b",
                "source_title": "Recovery Windows",
                "source_kind": "youtube",
                "segment": "08:22",
                "tags": ["back-fencing", "recovery", "regrowth"],
                "category": "grazing-management",
            }
        )
    )
    assert len(updated["entry"]["sources"]) == 2

    searched = json.loads(
        handle_search_knowledge(
            {
                "query": "back fencing recovery",
                "author": "Greg Judy",
                "entry_type": "principle",
                "category": "grazing-management",
            }
        )
    )
    assert searched["entries"]
    assert searched["entries"][0]["id"] == entry_id

    sources = json.loads(handle_list_knowledge_sources({}))
    assert sources["count"] == 2


def test_queue_source_and_process_queue_tools():
    import pytest

    initialize()

    with pytest.raises(ValueError, match="FIRECRAWL_API_KEY"):
        handle_queue_source(
            {
                "url": "https://example.com/video-a",
                "author": "Greg Judy",
                "source_kind": "youtube",
            }
        )


def test_queue_source_and_process_queue_tools_with_firecrawl_key(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    initialize()

    queued = json.loads(
        handle_queue_source(
            {
                "url": "https://example.com/video-a",
                "author": "Greg Judy",
                "source_kind": "youtube",
            }
        )
    )
    assert queued["queued"] is True

    duplicate = json.loads(
        handle_queue_source(
            {
                "url": "https://example.com/video-a",
                "author": "Greg Judy",
                "source_kind": "youtube",
            }
        )
    )
    assert duplicate["queued"] is False
    assert duplicate["reason"] == "already_queued"

    popped = json.loads(handle_process_queue({}))
    assert popped["count"] == 1
    assert popped["items"][0]["url"] == "https://example.com/video-a"

    empty = json.loads(handle_process_queue({}))
    assert empty["count"] == 0


def test_ingestion_batch_runner_tools():
    import pytest

    initialize()

    with pytest.raises(ValueError, match="FIRECRAWL_API_KEY"):
        handle_create_ingestion_batch(
            {
                "batch_name": "Greg Judy Test Batch",
                "author": "Greg Judy",
                "source_kind": "youtube",
                "sources": [
                    {
                        "url": "https://example.com/video-a",
                        "source_title": "Video A",
                    }
                ],
            }
        )


def test_ingestion_batch_runner_tools_with_firecrawl_key(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    initialize()

    created = json.loads(
        handle_create_ingestion_batch(
            {
                "batch_name": "Greg Judy Test Batch",
                "author": "Greg Judy",
                "source_kind": "youtube",
                "sources": [
                    {
                        "url": "https://example.com/video-a",
                        "source_title": "Video A",
                    },
                    {
                        "url": "https://example.com/video-b",
                        "source_title": "Video B",
                    },
                ],
            }
        )
    )
    batch = created["batch"]
    assert batch["summary"]["requested_sources"] == 2
    assert batch["summary"]["queued_sources"] == 2

    claimed = json.loads(handle_claim_ingestion_batch_item({"batch_id": batch["id"]}))
    assert claimed["count"] == 1
    assert claimed["item"]["url"] == "https://example.com/video-a"
    assert claimed["batch"]["summary"]["claimed_sources"] == 1

    recorded = json.loads(
        handle_record_ingestion_batch_result(
            {
                "batch_id": batch["id"],
                "url": "https://example.com/video-a",
                "status": "completed",
                "stored_count": 3,
                "entry_ids": ["knowledge_1", "knowledge_2", "knowledge_3"],
                "note": "Stored three lessons.",
            }
        )
    )
    assert recorded["batch"]["summary"]["completed_sources"] == 1
    assert recorded["batch"]["summary"]["stored_lessons"] == 3

    status = json.loads(handle_get_ingestion_batch_status({"batch_id": batch["id"]}))
    assert status["batch"]["summary"]["queued_sources"] == 1
    assert status["batch"]["status"] == "queued"
