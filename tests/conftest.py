"""Shared pytest fixtures for openPasture tests."""

from __future__ import annotations

import pytest

from openpasture.runtime import reset_runtime


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """Give each test an isolated local data directory."""
    monkeypatch.setenv("OPENPASTURE_DATA_DIR", str(tmp_path / ".openpasture"))
    monkeypatch.setenv("OPENPASTURE_STORE", "sqlite")
    monkeypatch.setenv("OPENPASTURE_LOAD_SEED", "0")
    reset_runtime()
    yield
    reset_runtime()
