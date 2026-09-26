"""Databases created before the decision record must still load."""

from __future__ import annotations

import sqlite3

from openpasture.store.sqlite import SQLiteStore

LEGACY_SCHEMA = """
CREATE TABLE farms (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, timezone TEXT NOT NULL, boundary_geojson TEXT,
    location_geojson TEXT, herd_ids TEXT NOT NULL, water_sources TEXT NOT NULL, notes TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE observations (
    id TEXT PRIMARY KEY, farm_id TEXT NOT NULL, source TEXT NOT NULL, observed_at TEXT NOT NULL,
    content TEXT NOT NULL, paddock_id TEXT, herd_id TEXT, metrics TEXT NOT NULL, media_url TEXT,
    tags TEXT NOT NULL
);
CREATE TABLE movement_decisions (
    id TEXT PRIMARY KEY, farm_id TEXT NOT NULL, herd_id TEXT, for_date TEXT NOT NULL, action TEXT NOT NULL,
    reasoning TEXT NOT NULL, confidence TEXT NOT NULL, source_paddock_id TEXT, target_paddock_id TEXT,
    knowledge_entry_ids TEXT NOT NULL, status TEXT NOT NULL, farmer_feedback TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY(farm_id) REFERENCES farms(id)
);
CREATE TABLE daily_briefs (
    id TEXT PRIMARY KEY, farm_id TEXT NOT NULL, generated_at TEXT NOT NULL, summary TEXT NOT NULL,
    recommendation_id TEXT NOT NULL, uncertainty_request TEXT, highlights TEXT NOT NULL,
    FOREIGN KEY(farm_id) REFERENCES farms(id),
    FOREIGN KEY(recommendation_id) REFERENCES movement_decisions(id)
);
"""


def _legacy_db(tmp_path):
    data_dir = tmp_path / ".openpasture"
    data_dir.mkdir()
    with sqlite3.connect(data_dir / "farm.db") as connection:
        connection.executescript(LEGACY_SCHEMA)
        connection.execute(
            "INSERT INTO farms VALUES ('farm_1', 'Old Farm', 'America/Chicago', NULL, NULL, '[\"herd_1\"]', '[]', '', '2026-05-01T12:00:00')"
        )
        connection.execute(
            "INSERT INTO observations VALUES ('obs_old', 'farm_1', 'field', '2026-05-01T12:00:00', 'Short.', 'p1', 'herd_1', '{}', NULL, '[]')"
        )
        connection.execute(
            """
            INSERT INTO movement_decisions VALUES
            ('plan_old', 'farm_1', 'herd_1', '2026-05-02', 'MOVE', '["Paddock is short."]', 'medium',
             'p1', 'p2', '["ke_1"]', 'pending', NULL, '2026-05-02T11:00:00.123456'),
            ('plan_done', 'farm_1', 'herd_1', '2026-05-01', 'MOVE', '["Moved."]', 'high',
             'p0', 'p1', '[]', 'approved', 'Moved them after lunch.', '2026-05-01T11:00:00')
            """
        )
        connection.execute(
            "INSERT INTO daily_briefs VALUES ('brief_old', 'farm_1', '2026-05-02T11:00:00', 'Move today.', 'plan_old', NULL, '[]')"
        )
    return data_dir


def test_bootstrap_migrates_old_plan_rows_and_briefs(tmp_path):
    store = SQLiteStore(_legacy_db(tmp_path))
    store.bootstrap()

    decision = store.get_decision("plan_old")
    assert decision is not None
    assert decision.status == "proposed"  # was "pending"
    assert decision.autonomy == "propose"
    assert decision.decided_by == "legacy"
    assert (decision.from_land_unit_id, decision.to_land_unit_id) == ("p1", "p2")
    assert decision.inputs.knowledge_entry_ids == ["ke_1"]
    assert decision.window.starts_at.isoformat() == "2026-05-02T00:00:00-05:00"
    assert decision.window.ends_at.isoformat() == "2026-05-03T00:00:00-05:00"

    done = store.get_decision("plan_done")
    assert done.status == "approved"
    assert done.farmer_response is not None
    assert done.farmer_response.note == "Moved them after lunch."

    brief = store.get_daily_brief("brief_old")
    assert brief is not None and brief.decision.decision_id == "plan_old"

    assert store.get_latest_decision("farm_1").decision_id == "plan_old"
    assert store.get_recent_observations("farm_1", days=100_000)[0].provenance == {}

    with sqlite3.connect(store.db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "movement_decisions" not in tables
    assert "movement_decisions_legacy" in tables  # kept, not dropped

    # Bootstrapping again is a no-op.
    store.bootstrap()
    assert len(store.list_decisions("farm_1")) == 2
