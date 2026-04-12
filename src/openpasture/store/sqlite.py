"""SQLite backend for self-hosted openPasture deployments."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from openpasture.domain import (
    DailyBrief,
    Farm,
    GeoPoint,
    GeoPolygon,
    Herd,
    MovementDecision,
    Observation,
    Paddock,
    WaterSource,
)


def _json_dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def _datetime_to_text(value: datetime) -> str:
    return value.isoformat()


def _date_to_text(value: date) -> str:
    return value.isoformat()


def _datetime_from_text(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _date_from_text(value: str) -> date:
    return date.fromisoformat(value)


def _serialize_point(point: GeoPoint | None) -> str | None:
    return None if point is None else _json_dumps(point.to_geojson())


def _serialize_polygon(polygon: GeoPolygon | None) -> str | None:
    return None if polygon is None else _json_dumps(polygon.to_geojson())


def _deserialize_point(value: str | None) -> GeoPoint | None:
    return None if not value else GeoPoint.from_geojson(json.loads(value))


def _deserialize_polygon(value: str | None) -> GeoPolygon | None:
    return None if not value else GeoPolygon.from_geojson(json.loads(value))


def _serialize_water_sources(water_sources: list[WaterSource]) -> str:
    payload = []
    for source in water_sources:
        payload.append(
            {
                "id": source.id,
                "name": source.name,
                "location": source.location.to_geojson() if source.location else None,
                "notes": source.notes,
            }
        )
    return _json_dumps(payload)


def _deserialize_water_sources(value: str | None) -> list[WaterSource]:
    sources = []
    for raw_source in _json_loads(value, []):
        sources.append(
            WaterSource(
                id=raw_source["id"],
                name=raw_source["name"],
                location=GeoPoint.from_geojson(raw_source["location"]) if raw_source.get("location") else None,
                notes=raw_source.get("notes", ""),
            )
        )
    return sources


class SQLiteStore:
    """SQLite-backed implementation of the FarmStore protocol."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "farm.db"

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def bootstrap(self) -> None:
        """Prepare local storage files for a self-hosted install."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS farms (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    boundary_geojson TEXT,
                    location_geojson TEXT,
                    paddock_ids TEXT NOT NULL,
                    herd_ids TEXT NOT NULL,
                    water_sources TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paddocks (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    geometry TEXT NOT NULL,
                    area_hectares REAL,
                    notes TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(farm_id) REFERENCES farms(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS herds (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL,
                    species TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    current_paddock_id TEXT,
                    animal_units REAL,
                    notes TEXT NOT NULL,
                    FOREIGN KEY(farm_id) REFERENCES farms(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    content TEXT NOT NULL,
                    paddock_id TEXT,
                    herd_id TEXT,
                    metrics TEXT NOT NULL,
                    media_url TEXT,
                    tags TEXT NOT NULL,
                    FOREIGN KEY(farm_id) REFERENCES farms(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS movement_decisions (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL,
                    herd_id TEXT,
                    for_date TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    source_paddock_id TEXT,
                    target_paddock_id TEXT,
                    knowledge_entry_ids TEXT NOT NULL,
                    status TEXT NOT NULL,
                    farmer_feedback TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(farm_id) REFERENCES farms(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_briefs (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    recommendation_id TEXT NOT NULL,
                    uncertainty_request TEXT,
                    highlights TEXT NOT NULL,
                    FOREIGN KEY(farm_id) REFERENCES farms(id),
                    FOREIGN KEY(recommendation_id) REFERENCES movement_decisions(id)
                )
                """
            )

    def _farm_from_row(self, row: sqlite3.Row) -> Farm:
        return Farm(
            id=row["id"],
            name=row["name"],
            timezone=row["timezone"],
            boundary=_deserialize_polygon(row["boundary_geojson"]),
            location=_deserialize_point(row["location_geojson"]),
            paddock_ids=_json_loads(row["paddock_ids"], []),
            herd_ids=_json_loads(row["herd_ids"], []),
            water_sources=_deserialize_water_sources(row["water_sources"]),
            notes=row["notes"],
            created_at=_datetime_from_text(row["created_at"]),
        )

    def _paddock_from_row(self, row: sqlite3.Row) -> Paddock:
        polygon = _deserialize_polygon(row["geometry"])
        if polygon is None:
            raise ValueError("Paddock geometry cannot be null.")
        return Paddock(
            id=row["id"],
            farm_id=row["farm_id"],
            name=row["name"],
            geometry=polygon,
            area_hectares=row["area_hectares"],
            notes=row["notes"],
            status=row["status"],
        )

    def _herd_from_row(self, row: sqlite3.Row) -> Herd:
        return Herd(
            id=row["id"],
            farm_id=row["farm_id"],
            species=row["species"],
            count=row["count"],
            current_paddock_id=row["current_paddock_id"],
            animal_units=row["animal_units"],
            notes=row["notes"],
        )

    def _observation_from_row(self, row: sqlite3.Row) -> Observation:
        return Observation(
            id=row["id"],
            farm_id=row["farm_id"],
            source=row["source"],
            observed_at=_datetime_from_text(row["observed_at"]),
            content=row["content"],
            paddock_id=row["paddock_id"],
            herd_id=row["herd_id"],
            metrics=_json_loads(row["metrics"], {}),
            media_url=row["media_url"],
            tags=_json_loads(row["tags"], []),
        )

    def _plan_from_row(self, row: sqlite3.Row) -> MovementDecision:
        return MovementDecision(
            id=row["id"],
            farm_id=row["farm_id"],
            herd_id=row["herd_id"],
            for_date=_date_from_text(row["for_date"]),
            action=row["action"],
            reasoning=_json_loads(row["reasoning"], []),
            confidence=row["confidence"],
            source_paddock_id=row["source_paddock_id"],
            target_paddock_id=row["target_paddock_id"],
            knowledge_entry_ids=_json_loads(row["knowledge_entry_ids"], []),
            status=row["status"],
            farmer_feedback=row["farmer_feedback"],
            created_at=_datetime_from_text(row["created_at"]),
        )

    def _daily_brief_from_row(self, row: sqlite3.Row) -> DailyBrief:
        recommendation = self.get_plan(row["recommendation_id"])
        if recommendation is None:
            raise ValueError("Daily brief references a missing recommendation.")
        return DailyBrief(
            id=row["id"],
            farm_id=row["farm_id"],
            generated_at=_datetime_from_text(row["generated_at"]),
            summary=row["summary"],
            recommendation=recommendation,
            uncertainty_request=row["uncertainty_request"],
            highlights=_json_loads(row["highlights"], []),
        )

    def _append_farm_reference(self, connection: sqlite3.Connection, farm_id: str, column: str, item_id: str) -> None:
        row = connection.execute(f"SELECT {column} FROM farms WHERE id = ?", (farm_id,)).fetchone()
        if row is None:
            raise ValueError(f"Farm '{farm_id}' does not exist.")
        values = _json_loads(row[column], [])
        if item_id not in values:
            values.append(item_id)
            connection.execute(
                f"UPDATE farms SET {column} = ? WHERE id = ?",
                (_json_dumps(values), farm_id),
            )

    def get_farm(self, farm_id: str) -> Farm | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM farms WHERE id = ?", (farm_id,)).fetchone()
        return None if row is None else self._farm_from_row(row)

    def list_farms(self) -> list[Farm]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM farms ORDER BY name ASC").fetchall()
        return [self._farm_from_row(row) for row in rows]

    def create_farm(self, farm: Farm) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO farms (
                    id, name, timezone, boundary_geojson, location_geojson, paddock_ids,
                    herd_ids, water_sources, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    farm.id,
                    farm.name,
                    farm.timezone,
                    _serialize_polygon(farm.boundary),
                    _serialize_point(farm.location),
                    _json_dumps(farm.paddock_ids),
                    _json_dumps(farm.herd_ids),
                    _serialize_water_sources(farm.water_sources),
                    farm.notes,
                    _datetime_to_text(farm.created_at),
                ),
            )
        return farm.id

    def update_farm(self, farm_id: str, **updates: object) -> None:
        if not updates:
            return

        column_map = {
            "name": "name",
            "timezone": "timezone",
            "boundary": "boundary_geojson",
            "location": "location_geojson",
            "paddock_ids": "paddock_ids",
            "herd_ids": "herd_ids",
            "water_sources": "water_sources",
            "notes": "notes",
        }

        assignments: list[str] = []
        values: list[object] = []
        for key, value in updates.items():
            if key not in column_map:
                continue
            column = column_map[key]
            if key == "boundary":
                value = _serialize_polygon(value if isinstance(value, GeoPolygon) else None)
            elif key == "location":
                value = _serialize_point(value if isinstance(value, GeoPoint) else None)
            elif key in {"paddock_ids", "herd_ids"}:
                value = _json_dumps(value)
            elif key == "water_sources":
                value = _serialize_water_sources(value if isinstance(value, list) else [])
            assignments.append(f"{column} = ?")
            values.append(value)

        if not assignments:
            return

        values.append(farm_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE farms SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )

    def get_paddock(self, paddock_id: str) -> Paddock | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM paddocks WHERE id = ?", (paddock_id,)).fetchone()
        return None if row is None else self._paddock_from_row(row)

    def list_paddocks(self, farm_id: str) -> list[Paddock]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM paddocks WHERE farm_id = ? ORDER BY name ASC",
                (farm_id,),
            ).fetchall()
        return [self._paddock_from_row(row) for row in rows]

    def create_paddock(self, paddock: Paddock) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO paddocks (id, farm_id, name, geometry, area_hectares, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paddock.id,
                    paddock.farm_id,
                    paddock.name,
                    _serialize_polygon(paddock.geometry),
                    paddock.area_hectares,
                    paddock.notes,
                    paddock.status,
                ),
            )
            self._append_farm_reference(connection, paddock.farm_id, "paddock_ids", paddock.id)
        return paddock.id

    def create_herd(self, herd: Herd) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO herds (id, farm_id, species, count, current_paddock_id, animal_units, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    herd.id,
                    herd.farm_id,
                    herd.species,
                    herd.count,
                    herd.current_paddock_id,
                    herd.animal_units,
                    herd.notes,
                ),
            )
            self._append_farm_reference(connection, herd.farm_id, "herd_ids", herd.id)
        return herd.id

    def get_herds(self, farm_id: str) -> list[Herd]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM herds WHERE farm_id = ? ORDER BY species ASC, id ASC",
                (farm_id,),
            ).fetchall()
        return [self._herd_from_row(row) for row in rows]

    def update_herd_position(self, herd_id: str, paddock_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE herds SET current_paddock_id = ? WHERE id = ?",
                (paddock_id, herd_id),
            )

    def record_observation(self, observation: Observation) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO observations (
                    id, farm_id, source, observed_at, content, paddock_id, herd_id, metrics, media_url, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.id,
                    observation.farm_id,
                    observation.source,
                    _datetime_to_text(observation.observed_at),
                    observation.content,
                    observation.paddock_id,
                    observation.herd_id,
                    _json_dumps(observation.metrics),
                    observation.media_url,
                    _json_dumps(observation.tags),
                ),
            )
        return observation.id

    def get_recent_observations(self, farm_id: str, days: int = 7) -> list[Observation]:
        cutoff = _datetime_to_text(datetime.utcnow() - timedelta(days=days))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM observations
                WHERE farm_id = ? AND observed_at >= ?
                ORDER BY observed_at DESC
                """,
                (farm_id, cutoff),
            ).fetchall()
        return [self._observation_from_row(row) for row in rows]

    def get_paddock_observations(self, paddock_id: str, days: int = 7) -> list[Observation]:
        cutoff = _datetime_to_text(datetime.utcnow() - timedelta(days=days))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM observations
                WHERE paddock_id = ? AND observed_at >= ?
                ORDER BY observed_at DESC
                """,
                (paddock_id, cutoff),
            ).fetchall()
        return [self._observation_from_row(row) for row in rows]

    def create_plan(self, plan: MovementDecision) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO movement_decisions (
                    id, farm_id, herd_id, for_date, action, reasoning, confidence, source_paddock_id,
                    target_paddock_id, knowledge_entry_ids, status, farmer_feedback, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.id,
                    plan.farm_id,
                    plan.herd_id,
                    _date_to_text(plan.for_date),
                    plan.action,
                    _json_dumps(plan.reasoning),
                    plan.confidence,
                    plan.source_paddock_id,
                    plan.target_paddock_id,
                    _json_dumps(plan.knowledge_entry_ids),
                    plan.status,
                    plan.farmer_feedback,
                    _datetime_to_text(plan.created_at),
                ),
            )
        return plan.id

    def get_plan(self, plan_id: str) -> MovementDecision | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM movement_decisions WHERE id = ?",
                (plan_id,),
            ).fetchone()
        return None if row is None else self._plan_from_row(row)

    def get_latest_plan(self, farm_id: str) -> MovementDecision | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM movement_decisions
                WHERE farm_id = ?
                ORDER BY for_date DESC, created_at DESC
                LIMIT 1
                """,
                (farm_id,),
            ).fetchone()
        return None if row is None else self._plan_from_row(row)

    def update_plan_status(self, plan_id: str, status: str, feedback: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE movement_decisions
                SET status = ?, farmer_feedback = COALESCE(?, farmer_feedback)
                WHERE id = ?
                """,
                (status, feedback, plan_id),
            )

    def save_daily_brief(self, brief: DailyBrief) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO daily_briefs (
                    id, farm_id, generated_at, summary, recommendation_id, uncertainty_request, highlights
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    brief.id,
                    brief.farm_id,
                    _datetime_to_text(brief.generated_at),
                    brief.summary,
                    brief.recommendation.id,
                    brief.uncertainty_request,
                    _json_dumps(brief.highlights),
                ),
            )
        return brief.id

    def get_daily_brief(self, brief_id: str) -> DailyBrief | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM daily_briefs WHERE id = ?",
                (brief_id,),
            ).fetchone()
        return None if row is None else self._daily_brief_from_row(row)
