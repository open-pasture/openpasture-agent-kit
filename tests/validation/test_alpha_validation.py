from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from openpasture.validation.alpha import backup_and_restore_sqlite_data_dir, load_validation_config

pytestmark = pytest.mark.alpha


def _init_sqlite(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, note TEXT)")
        connection.execute("INSERT INTO sample (note) VALUES (?)", (path.name,))


def test_load_validation_config_reads_tested_hermes_target():
    config = load_validation_config()

    assert config.tested_hermes_version == "0.8.0"
    assert config.tested_hermes_commit == "1cec910b6a064d4e4821930be5cfaaf6145a2afd"


def test_backup_and_restore_sqlite_data_dir_round_trips_databases(tmp_path):
    data_dir = tmp_path / "openpasture-data"
    data_dir.mkdir()
    _init_sqlite(data_dir / "farm.db")
    _init_sqlite(data_dir / "knowledge.db")

    archive_path, restored_dir = backup_and_restore_sqlite_data_dir(data_dir, tmp_path / "work")

    assert archive_path.exists()
    assert (restored_dir / "farm.db").exists()
    assert (restored_dir / "knowledge.db").exists()
