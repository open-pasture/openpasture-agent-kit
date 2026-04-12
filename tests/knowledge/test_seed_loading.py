from __future__ import annotations

from datetime import datetime

import pytest

import openpasture.runtime as runtime
from openpasture.domain import KnowledgeEntry, SourceRecord
from openpasture.runtime import get_knowledge_store, init_knowledge_store, initialize

pytestmark = pytest.mark.alpha


def test_initialize_autoloads_seed_on_first_run(monkeypatch):
    monkeypatch.delenv("OPENPASTURE_LOAD_SEED", raising=False)

    initialize()

    assert get_knowledge_store().count() > 0


def test_initialize_skips_autoload_when_store_already_has_entries(monkeypatch):
    monkeypatch.delenv("OPENPASTURE_LOAD_SEED", raising=False)

    store = init_knowledge_store()
    store.store_entries(
        [
            KnowledgeEntry(
                id="knowledge_existing",
                farm_id=None,
                entry_type="principle",
                content="Existing local knowledge should not trigger seed reload.",
                sources=[
                    SourceRecord(
                        source_url="https://example.com/existing",
                        source_title="Existing Entry",
                        source_author="Local Farmer",
                        source_kind="manual",
                    )
                ],
                created_at=datetime.utcnow(),
                tags=["local"],
                category="grazing-management",
            )
        ]
    )

    def fail_loader(*args, **kwargs):
        raise AssertionError("Seed loader should not run when knowledge.db already has entries.")

    monkeypatch.setattr(runtime, "load_seed_knowledge", fail_loader)

    initialize()

    assert get_knowledge_store().count() == 1


def test_openpasture_load_seed_zero_skips_first_run(monkeypatch):
    monkeypatch.setenv("OPENPASTURE_LOAD_SEED", "0")

    initialize()

    assert get_knowledge_store().count() == 0


def test_openpasture_load_seed_one_forces_reload(monkeypatch):
    monkeypatch.setenv("OPENPASTURE_LOAD_SEED", "1")

    store = init_knowledge_store()
    store.store_entries(
        [
            KnowledgeEntry(
                id="knowledge_existing",
                farm_id=None,
                entry_type="principle",
                content="Existing local knowledge should not block a forced reload.",
                sources=[
                    SourceRecord(
                        source_url="https://example.com/existing",
                        source_title="Existing Entry",
                        source_author="Local Farmer",
                        source_kind="manual",
                    )
                ],
                created_at=datetime.utcnow(),
                tags=["local"],
                category="grazing-management",
            )
        ]
    )

    calls = {"count": 0}

    def fake_loader(*args, **kwargs):
        calls["count"] += 1
        return []

    monkeypatch.setattr(runtime, "load_seed_knowledge", fake_loader)

    initialize()

    assert calls["count"] == 1
