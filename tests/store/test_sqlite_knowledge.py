from __future__ import annotations

from datetime import datetime

from openpasture.domain import KnowledgeEntry, SourceRecord
from openpasture.store.sqlite_knowledge import SQLiteKnowledgeStore


def build_store(tmp_path) -> SQLiteKnowledgeStore:
    store = SQLiteKnowledgeStore(tmp_path / ".openpasture")
    store.bootstrap()
    return store


def test_sqlite_knowledge_store_round_trips_entries_and_sources(tmp_path):
    store = build_store(tmp_path)
    entry = KnowledgeEntry(
        id="knowledge_1",
        farm_id=None,
        entry_type="principle",
        category="grazing-management",
        content="Leave residual and move before animals reglaze fresh regrowth.",
        sources=[
            SourceRecord(
                source_url="seed://universal",
                source_title="Universal Principles",
                source_author="openPasture",
                source_kind="seed",
                segment="Top Third Rule",
            )
        ],
        tags=["residual", "movement"],
        embedding_id="knowledge_1",
    )

    assert store.store_entries([entry]) == [entry.id]

    loaded = store.get_entry(entry.id)
    assert loaded is not None
    assert loaded.content == entry.content
    assert loaded.category == "grazing-management"
    assert loaded.primary_author == "openPasture"

    results = store.search("residual move", limit=5)
    assert results
    assert results[0].id == entry.id

    sources = store.list_sources()
    assert len(sources) == 1
    assert sources[0].segment == "Top Third Rule"
    assert store.count() == 1


def test_sqlite_knowledge_store_updates_entries_and_filters_by_author(tmp_path):
    store = build_store(tmp_path)
    original = KnowledgeEntry(
        id="knowledge_1",
        farm_id=None,
        entry_type="technique",
        category="products",
        content="Polywire reels speed up daily moves.",
        sources=[
            SourceRecord(
                source_url="https://example.com/video-a",
                source_title="Daily Moves",
                source_author="Greg Judy",
                source_kind="youtube",
            )
        ],
        tags=["polywire"],
        created_at=datetime.utcnow(),
        embedding_id="knowledge_1",
    )
    store.store_entries([original])

    updated = KnowledgeEntry(
        id=original.id,
        farm_id=None,
        entry_type=original.entry_type,
        category="products",
        content="Polywire reels and geared reels both speed up daily moves when labor is tight.",
        sources=original.sources
        + [
            SourceRecord(
                source_url="https://example.com/video-b",
                source_title="Labor Saving Tools",
                source_author="Greg Judy",
                source_kind="youtube",
            )
        ],
        tags=["polywire", "geared-reel"],
        created_at=original.created_at,
        embedding_id=original.embedding_id,
    )
    store.update_entry(updated)

    author_entries = store.get_entries_by_author("Greg Judy")
    assert len(author_entries) == 1
    assert len(author_entries[0].sources) == 2

    filtered = store.search(
        "labor",
        limit=5,
        authors=["Greg Judy"],
        categories=["products"],
        entry_types=["technique"],
    )
    assert len(filtered) == 1
    assert filtered[0].id == original.id
