"""SQLite backend for self-hosted openPasture deployments."""

from __future__ import annotations

import json
import sqlite3
from uuid import uuid4
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from openpasture.domain import (
    Animal,
    DailyBrief,
    DataPipeline,
    Farm,
    FarmActivityAttachment,
    FarmActivityEvent,
    FarmActivityTarget,
    FarmerAction,
    GeoFeature,
    GeoPoint,
    GeoPolygon,
    Herd,
    LandUnit,
    MovementDecision,
    Observation,
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


def _deserialize_point(value: str | None) -> GeoPoint | None:
    return None if not value else GeoPoint.from_geojson(json.loads(value))


def _serialize_geo_feature(feature: GeoFeature | None) -> str | None:
    return None if feature is None else _json_dumps(feature.to_geojson())


def _deserialize_geo_feature(value: str | None) -> GeoFeature | None:
    return None if not value else GeoFeature.from_geojson(json.loads(value))


def _serialize_boundary(boundary: GeoFeature | GeoPolygon | None) -> str | None:
    if boundary is None:
        return None
    return _json_dumps(boundary.to_geojson())


def _deserialize_boundary(value: str | None) -> GeoFeature | None:
    return None if not value else GeoFeature.from_geojson(json.loads(value))


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
                    herd_ids TEXT NOT NULL,
                    water_sources TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS land_units (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL,
                    parent_id TEXT,
                    unit_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    geometry_geojson TEXT NOT NULL,
                    area_hectares REAL,
                    confidence REAL NOT NULL,
                    provenance TEXT NOT NULL,
                    geometry_version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    warnings TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(farm_id) REFERENCES farms(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_land_units_farm_type ON land_units(farm_id, unit_type)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_land_units_parent ON land_units(parent_id)"
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
                CREATE TABLE IF NOT EXISTS animals (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL,
                    herd_id TEXT,
                    species TEXT NOT NULL,
                    sex TEXT NOT NULL,
                    name TEXT,
                    tag TEXT NOT NULL,
                    secondary_tags TEXT NOT NULL,
                    breed TEXT,
                    birth_date TEXT,
                    dam_id TEXT,
                    sire_id TEXT,
                    status TEXT NOT NULL,
                    current_paddock_id TEXT,
                    notes TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(farm_id) REFERENCES farms(id),
                    FOREIGN KEY(herd_id) REFERENCES herds(id)
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_animals_farm ON animals(farm_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_animals_herd ON animals(herd_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_animals_farm_tag ON animals(farm_id, tag)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_animals_farm_status ON animals(farm_id, status)")
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
                CREATE TABLE IF NOT EXISTS farm_activity_events (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    summary TEXT,
                    payload TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    visibility TEXT NOT NULL,
                    FOREIGN KEY(farm_id) REFERENCES farms(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_events_farm_occurred ON farm_activity_events(farm_id, occurred_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS farm_activity_targets (
                    activity_id TEXT NOT NULL,
                    farm_id TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    PRIMARY KEY(activity_id, subject_type, subject_id, relationship),
                    FOREIGN KEY(activity_id) REFERENCES farm_activity_events(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_targets_subject ON farm_activity_targets(subject_type, subject_id, occurred_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_targets_farm ON farm_activity_targets(farm_id, occurred_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS farm_activity_attachments (
                    id TEXT PRIMARY KEY,
                    activity_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    file_name TEXT,
                    content_type TEXT,
                    metadata TEXT NOT NULL,
                    FOREIGN KEY(activity_id) REFERENCES farm_activity_events(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_attachments_activity ON farm_activity_attachments(activity_id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS data_pipelines (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    login_url TEXT NOT NULL,
                    target_urls TEXT NOT NULL,
                    extraction_prompts TEXT NOT NULL,
                    observation_source TEXT NOT NULL,
                    observation_tags TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    vendor_skill_version TEXT,
                    enabled INTEGER NOT NULL,
                    last_collected_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(farm_id) REFERENCES farms(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS farmer_actions (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    context TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolution TEXT,
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
            boundary=_deserialize_boundary(row["boundary_geojson"]),
            location=_deserialize_point(row["location_geojson"]),
            herd_ids=_json_loads(row["herd_ids"], []),
            water_sources=_deserialize_water_sources(row["water_sources"]),
            notes=row["notes"],
            created_at=_datetime_from_text(row["created_at"]),
        )

    def _land_unit_from_row(self, row: sqlite3.Row) -> LandUnit:
        feature = _deserialize_geo_feature(row["geometry_geojson"])
        if feature is None:
            raise ValueError("Land unit geometry cannot be null.")
        return LandUnit(
            id=row["id"],
            farm_id=row["farm_id"],
            parent_id=row["parent_id"],
            unit_type=row["unit_type"],
            name=row["name"],
            geometry=feature,
            area_hectares=row["area_hectares"],
            confidence=row["confidence"],
            provenance=_json_loads(row["provenance"], {}),
            geometry_version=row["geometry_version"],
            status=row["status"],
            notes=row["notes"],
            warnings=_json_loads(row["warnings"], []),
            created_at=_datetime_from_text(row["created_at"]),
            updated_at=_datetime_from_text(row["updated_at"]),
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

    def _animal_from_row(self, row: sqlite3.Row) -> Animal:
        return Animal(
            id=row["id"],
            farm_id=row["farm_id"],
            herd_id=row["herd_id"],
            species=row["species"],
            sex=row["sex"],
            name=row["name"],
            tag=row["tag"],
            secondary_tags=_json_loads(row["secondary_tags"], []),
            breed=row["breed"],
            birth_date=row["birth_date"],
            dam_id=row["dam_id"],
            sire_id=row["sire_id"],
            status=row["status"],
            current_paddock_id=row["current_paddock_id"],
            notes=row["notes"],
            metadata=_json_loads(row["metadata"], {}),
            created_at=_datetime_from_text(row["created_at"]),
            updated_at=_datetime_from_text(row["updated_at"]),
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

    def _activity_from_row(self, connection: sqlite3.Connection, row: sqlite3.Row) -> FarmActivityEvent:
        target_rows = connection.execute(
            """
            SELECT * FROM farm_activity_targets
            WHERE activity_id = ?
            ORDER BY relationship ASC, subject_type ASC, subject_id ASC
            """,
            (row["id"],),
        ).fetchall()
        attachment_rows = connection.execute(
            """
            SELECT * FROM farm_activity_attachments
            WHERE activity_id = ?
            ORDER BY id ASC
            """,
            (row["id"],),
        ).fetchall()
        return FarmActivityEvent(
            id=row["id"],
            farm_id=row["farm_id"],
            event_type=row["event_type"],
            source=row["source"],
            occurred_at=_datetime_from_text(row["occurred_at"]),
            recorded_at=_datetime_from_text(row["recorded_at"]),
            title=row["title"],
            body=row["body"],
            summary=row["summary"],
            payload=_json_loads(row["payload"], {}),
            provenance=_json_loads(row["provenance"], {}),
            visibility=row["visibility"],
            targets=[
                FarmActivityTarget(
                    subject_type=target["subject_type"],
                    subject_id=target["subject_id"],
                    relationship=target["relationship"],
                )
                for target in target_rows
            ],
            attachments=[
                FarmActivityAttachment(
                    id=attachment["id"],
                    url=attachment["url"],
                    media_type=attachment["media_type"],
                    file_name=attachment["file_name"],
                    content_type=attachment["content_type"],
                    metadata=_json_loads(attachment["metadata"], {}),
                )
                for attachment in attachment_rows
            ],
        )

    def _pipeline_from_row(self, row: sqlite3.Row) -> DataPipeline:
        return DataPipeline(
            id=row["id"],
            farm_id=row["farm_id"],
            name=row["name"],
            profile_id=row["profile_id"],
            login_url=row["login_url"],
            target_urls=_json_loads(row["target_urls"], []),
            extraction_prompts=_json_loads(row["extraction_prompts"], []),
            observation_source=row["observation_source"],
            observation_tags=_json_loads(row["observation_tags"], []),
            schedule=row["schedule"],
            vendor_skill_version=row["vendor_skill_version"],
            enabled=bool(row["enabled"]),
            last_collected_at=(
                _datetime_from_text(row["last_collected_at"]) if row["last_collected_at"] else None
            ),
            last_error=row["last_error"],
            created_at=_datetime_from_text(row["created_at"]),
        )

    def _farmer_action_from_row(self, row: sqlite3.Row) -> FarmerAction:
        return FarmerAction(
            id=row["id"],
            farm_id=row["farm_id"],
            action_type=row["action_type"],
            summary=row["summary"],
            context=_json_loads(row["context"], {}),
            created_at=_datetime_from_text(row["created_at"]),
            resolved_at=_datetime_from_text(row["resolved_at"]) if row["resolved_at"] else None,
            resolution=row["resolution"],
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

    def _target_for_land_unit(self, land_unit_id: str, relationship: str = "primary") -> list[FarmActivityTarget]:
        unit = self.get_land_unit(land_unit_id)
        if unit is None:
            return [FarmActivityTarget(subject_type="paddock", subject_id=land_unit_id, relationship=relationship)]
        subject_type = unit.unit_type if unit.unit_type in {"pasture", "paddock"} else "land_unit"
        targets = [FarmActivityTarget(subject_type=subject_type, subject_id=unit.id, relationship=relationship)]
        if unit.parent_id:
            parent = self.get_land_unit(unit.parent_id)
            if parent and parent.unit_type == "pasture":
                targets.append(FarmActivityTarget(subject_type="pasture", subject_id=parent.id, relationship="parent"))
        return targets

    def _targets_from_context(self, farm_id: str, context: dict[str, object]) -> list[FarmActivityTarget]:
        targets = [FarmActivityTarget(subject_type="farm", subject_id=farm_id, relationship="farm")]
        for key, subject_type in (("paddock_id", "paddock"), ("herd_id", "herd"), ("animal_id", "animal")):
            value = context.get(key)
            if isinstance(value, str) and value:
                if subject_type == "paddock":
                    targets.extend(self._target_for_land_unit(value))
                else:
                    targets.append(FarmActivityTarget(subject_type=subject_type, subject_id=value))
        return targets

    def _record_system_activity(
        self,
        *,
        farm_id: str,
        event_type: str,
        source: str,
        title: str,
        body: str = "",
        occurred_at: datetime | None = None,
        payload: dict[str, object] | None = None,
        targets: list[FarmActivityTarget] | None = None,
        summary: str | None = None,
        provenance: dict[str, object] | None = None,
        attachments: list[FarmActivityAttachment] | None = None,
    ) -> str:
        event = FarmActivityEvent(
            id=f"activity_{uuid4().hex}",
            farm_id=farm_id,
            event_type=event_type,
            source=source,
            occurred_at=occurred_at or datetime.utcnow(),
            title=title,
            body=body,
            summary=summary,
            payload=payload or {},
            provenance=provenance or {"source": source},
            targets=targets or [FarmActivityTarget(subject_type="farm", subject_id=farm_id, relationship="farm")],
            attachments=attachments or [],
        )
        return self.record_activity_event(event)

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
                    id, name, timezone, boundary_geojson, location_geojson,
                    herd_ids, water_sources, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    farm.id,
                    farm.name,
                    farm.timezone,
                    _serialize_boundary(farm.boundary),
                    _serialize_point(farm.location),
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
                value = _serialize_boundary(value if isinstance(value, (GeoFeature, GeoPolygon)) else None)
            elif key == "location":
                value = _serialize_point(value if isinstance(value, GeoPoint) else None)
            elif key == "herd_ids":
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

    def get_land_unit(self, land_unit_id: str) -> LandUnit | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM land_units WHERE id = ?", (land_unit_id,)).fetchone()
        return None if row is None else self._land_unit_from_row(row)

    def list_land_units(self, farm_id: str, unit_type: str | None = None) -> list[LandUnit]:
        with self._connect() as connection:
            if unit_type is None:
                rows = connection.execute(
                    "SELECT * FROM land_units WHERE farm_id = ? ORDER BY unit_type ASC, name ASC",
                    (farm_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM land_units WHERE farm_id = ? AND unit_type = ? ORDER BY name ASC",
                    (farm_id, unit_type),
                ).fetchall()
        return [self._land_unit_from_row(row) for row in rows]

    def upsert_land_unit(self, land_unit: LandUnit) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO land_units (
                    id, farm_id, parent_id, unit_type, name, geometry_geojson, area_hectares,
                    confidence, provenance, geometry_version, status, notes, warnings, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    farm_id = excluded.farm_id,
                    parent_id = excluded.parent_id,
                    unit_type = excluded.unit_type,
                    name = excluded.name,
                    geometry_geojson = excluded.geometry_geojson,
                    area_hectares = excluded.area_hectares,
                    confidence = excluded.confidence,
                    provenance = excluded.provenance,
                    geometry_version = excluded.geometry_version,
                    status = excluded.status,
                    notes = excluded.notes,
                    warnings = excluded.warnings,
                    updated_at = excluded.updated_at
                """,
                (
                    land_unit.id,
                    land_unit.farm_id,
                    land_unit.parent_id,
                    land_unit.unit_type,
                    land_unit.name,
                    _serialize_geo_feature(land_unit.geometry),
                    land_unit.area_hectares,
                    land_unit.confidence,
                    _json_dumps(land_unit.provenance),
                    land_unit.geometry_version,
                    land_unit.status,
                    land_unit.notes,
                    _json_dumps(land_unit.warnings),
                    _datetime_to_text(land_unit.created_at),
                    _datetime_to_text(land_unit.updated_at),
                ),
            )
        return land_unit.id

    def update_land_unit(self, land_unit_id: str, **updates: object) -> None:
        existing = self.get_land_unit(land_unit_id)
        if existing is None:
            raise ValueError(f"Land unit '{land_unit_id}' does not exist.")
        if not updates:
            return

        column_map = {
            "parent_id": "parent_id",
            "name": "name",
            "geometry": "geometry_geojson",
            "area_hectares": "area_hectares",
            "confidence": "confidence",
            "provenance": "provenance",
            "geometry_version": "geometry_version",
            "status": "status",
            "notes": "notes",
            "warnings": "warnings",
            "updated_at": "updated_at",
        }
        assignments: list[str] = []
        values: list[object] = []
        for key, value in updates.items():
            if key not in column_map:
                continue
            if key == "geometry":
                value = _serialize_geo_feature(value if isinstance(value, GeoFeature) else None)
            elif key == "provenance":
                value = _json_dumps(value if isinstance(value, dict) else {})
            elif key == "warnings":
                value = _json_dumps(value if isinstance(value, list) else [])
            elif key == "updated_at":
                value = _datetime_to_text(value) if isinstance(value, datetime) else _datetime_to_text(datetime.utcnow())
            assignments.append(f"{column_map[key]} = ?")
            values.append(value)

        if "updated_at" not in updates:
            assignments.append("updated_at = ?")
            values.append(_datetime_to_text(datetime.utcnow()))

        if not assignments:
            return
        values.append(land_unit_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE land_units SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )

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
        herd = next((item for farm in self.list_farms() for item in self.get_herds(farm.id) if item.id == herd_id), None)
        if herd is not None:
            self._record_system_activity(
                farm_id=herd.farm_id,
                event_type="movement",
                source="herd_position",
                title="Herd moved",
                body=f"{herd.species} herd moved to {paddock_id}.",
                payload={"herd_id": herd_id, "target_paddock_id": paddock_id},
                targets=[
                    FarmActivityTarget(subject_type="herd", subject_id=herd_id),
                    *self._target_for_land_unit(paddock_id, relationship="target"),
                ],
            )

    def create_animal(self, animal: Animal) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO animals (
                    id, farm_id, herd_id, species, sex, name, tag, secondary_tags,
                    breed, birth_date, dam_id, sire_id, status, current_paddock_id,
                    notes, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    animal.id,
                    animal.farm_id,
                    animal.herd_id,
                    animal.species,
                    animal.sex,
                    animal.name,
                    animal.tag,
                    _json_dumps(animal.secondary_tags),
                    animal.breed,
                    animal.birth_date,
                    animal.dam_id,
                    animal.sire_id,
                    animal.status,
                    animal.current_paddock_id,
                    animal.notes,
                    _json_dumps(animal.metadata),
                    _datetime_to_text(animal.created_at),
                    _datetime_to_text(animal.updated_at),
                ),
            )
        self._record_system_activity(
            farm_id=animal.farm_id,
            event_type="animal_created",
            source="animal_record",
            title=f"Animal {animal.tag} added",
            body=animal.notes,
            payload={"animal_id": animal.id, "tag": animal.tag, "species": animal.species, "status": animal.status},
            targets=[
                FarmActivityTarget(subject_type="animal", subject_id=animal.id),
                *([FarmActivityTarget(subject_type="herd", subject_id=animal.herd_id)] if animal.herd_id else []),
            ],
        )
        return animal.id

    def get_animal(self, animal_id: str) -> Animal | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM animals WHERE id = ?", (animal_id,)).fetchone()
        return None if row is None else self._animal_from_row(row)

    def list_animals(self, farm_id: str, herd_id: str | None = None) -> list[Animal]:
        with self._connect() as connection:
            if herd_id is None:
                rows = connection.execute(
                    "SELECT * FROM animals WHERE farm_id = ? ORDER BY tag ASC, id ASC",
                    (farm_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM animals WHERE farm_id = ? AND herd_id = ? ORDER BY tag ASC, id ASC",
                    (farm_id, herd_id),
                ).fetchall()
        return [self._animal_from_row(row) for row in rows]

    def update_animal(self, animal_id: str, **updates: object) -> None:
        if not updates:
            return

        column_map = {
            "herd_id": "herd_id",
            "species": "species",
            "sex": "sex",
            "name": "name",
            "tag": "tag",
            "secondary_tags": "secondary_tags",
            "breed": "breed",
            "birth_date": "birth_date",
            "dam_id": "dam_id",
            "sire_id": "sire_id",
            "status": "status",
            "current_paddock_id": "current_paddock_id",
            "notes": "notes",
            "metadata": "metadata",
            "updated_at": "updated_at",
        }
        assignments: list[str] = []
        values: list[object] = []
        for key, value in updates.items():
            if key not in column_map:
                continue
            if key == "secondary_tags":
                value = _json_dumps(value if isinstance(value, list) else [])
            elif key == "metadata":
                value = _json_dumps(value if isinstance(value, dict) else {})
            elif key == "updated_at":
                value = _datetime_to_text(value) if isinstance(value, datetime) else _datetime_to_text(datetime.utcnow())
            assignments.append(f"{column_map[key]} = ?")
            values.append(value)

        if "updated_at" not in updates:
            assignments.append("updated_at = ?")
            values.append(_datetime_to_text(datetime.utcnow()))

        if not assignments:
            return
        values.append(animal_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE animals SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
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
        targets = [FarmActivityTarget(subject_type="farm", subject_id=observation.farm_id, relationship="farm")]
        if observation.paddock_id:
            targets.extend(self._target_for_land_unit(observation.paddock_id))
        if observation.herd_id:
            targets.append(FarmActivityTarget(subject_type="herd", subject_id=observation.herd_id))
        attachments = (
            [
                FarmActivityAttachment(
                    id=f"attachment_{observation.id}",
                    url=observation.media_url,
                    media_type="image" if observation.source in {"photo", "trailcam"} else "file",
                    metadata={"observation_id": observation.id},
                )
            ]
            if observation.media_url
            else []
        )
        self._record_system_activity(
            farm_id=observation.farm_id,
            event_type={
                "weather": "weather_report",
                "photo": "image_observation",
                "trailcam": "image_observation",
                "satellite": "imported_report",
            }.get(observation.source, "field_note"),
            source=observation.source,
            occurred_at=observation.observed_at,
            title=observation.content[:80] or "Observation recorded",
            body=observation.content,
            payload={
                "observation_id": observation.id,
                "metrics": observation.metrics,
                "tags": observation.tags,
            },
            targets=targets,
            attachments=attachments,
            provenance={"source": "observation", "observation_id": observation.id},
        )
        return observation.id

    def record_activity_event(self, event: FarmActivityEvent) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO farm_activity_events (
                    id, farm_id, event_type, source, occurred_at, recorded_at,
                    title, body, summary, payload, provenance, visibility
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.farm_id,
                    event.event_type,
                    event.source,
                    _datetime_to_text(event.occurred_at),
                    _datetime_to_text(event.recorded_at),
                    event.title,
                    event.body,
                    event.summary,
                    _json_dumps(event.payload),
                    _json_dumps(event.provenance),
                    event.visibility,
                ),
            )
            for target in event.targets:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO farm_activity_targets (
                        activity_id, farm_id, subject_type, subject_id, relationship, occurred_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.id,
                        event.farm_id,
                        target.subject_type,
                        target.subject_id,
                        target.relationship,
                        _datetime_to_text(event.occurred_at),
                    ),
                )
            for attachment in event.attachments:
                connection.execute(
                    """
                    INSERT INTO farm_activity_attachments (
                        id, activity_id, url, media_type, file_name, content_type, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        attachment.id,
                        event.id,
                        attachment.url,
                        attachment.media_type,
                        attachment.file_name,
                        attachment.content_type,
                        _json_dumps(attachment.metadata),
                    ),
                )
        return event.id

    def list_activity_feed(
        self,
        farm_id: str,
        subject_type: str,
        subject_id: str,
        limit: int = 50,
        before: str | None = None,
    ) -> list[FarmActivityEvent]:
        values: list[object] = [farm_id, subject_type, subject_id]
        before_clause = ""
        if before:
            before_clause = "AND t.occurred_at < ?"
            values.append(before)
        values.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT e.* FROM farm_activity_targets t
                JOIN farm_activity_events e ON e.id = t.activity_id
                WHERE t.farm_id = ? AND t.subject_type = ? AND t.subject_id = ?
                {before_clause}
                ORDER BY t.occurred_at DESC
                LIMIT ?
                """,
                tuple(values),
            ).fetchall()
            return [self._activity_from_row(connection, row) for row in rows]

    def list_animal_activity(self, animal_id: str, limit: int = 50) -> list[FarmActivityEvent]:
        animal = self.get_animal(animal_id)
        if animal is None:
            return []
        return self.list_activity_feed(animal.farm_id, "animal", animal_id, limit=limit)

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

    def create_pipeline(self, pipeline: DataPipeline) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO data_pipelines (
                    id, farm_id, name, profile_id, login_url, target_urls, extraction_prompts,
                    observation_source, observation_tags, schedule, vendor_skill_version,
                    enabled, last_collected_at, last_error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pipeline.id,
                    pipeline.farm_id,
                    pipeline.name,
                    pipeline.profile_id,
                    pipeline.login_url,
                    _json_dumps(pipeline.target_urls),
                    _json_dumps(pipeline.extraction_prompts),
                    pipeline.observation_source,
                    _json_dumps(pipeline.observation_tags),
                    pipeline.schedule,
                    pipeline.vendor_skill_version,
                    int(pipeline.enabled),
                    (
                        _datetime_to_text(pipeline.last_collected_at)
                        if pipeline.last_collected_at
                        else None
                    ),
                    pipeline.last_error,
                    _datetime_to_text(pipeline.created_at),
                ),
            )
        return pipeline.id

    def get_pipeline(self, pipeline_id: str) -> DataPipeline | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM data_pipelines WHERE id = ?",
                (pipeline_id,),
            ).fetchone()
        return None if row is None else self._pipeline_from_row(row)

    def list_pipelines(self, farm_id: str) -> list[DataPipeline]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM data_pipelines
                WHERE farm_id = ?
                ORDER BY name ASC, created_at ASC
                """,
                (farm_id,),
            ).fetchall()
        return [self._pipeline_from_row(row) for row in rows]

    def update_pipeline(self, pipeline_id: str, **updates: object) -> None:
        if not updates:
            return

        column_map = {
            "name": "name",
            "profile_id": "profile_id",
            "login_url": "login_url",
            "target_urls": "target_urls",
            "extraction_prompts": "extraction_prompts",
            "observation_source": "observation_source",
            "observation_tags": "observation_tags",
            "schedule": "schedule",
            "vendor_skill_version": "vendor_skill_version",
            "enabled": "enabled",
            "last_collected_at": "last_collected_at",
            "last_error": "last_error",
        }

        assignments: list[str] = []
        values: list[object] = []
        for key, value in updates.items():
            if key not in column_map:
                continue
            if key in {"target_urls", "extraction_prompts", "observation_tags"}:
                value = _json_dumps(value if isinstance(value, list) else [])
            elif key == "enabled":
                value = int(bool(value))
            elif key == "last_collected_at":
                value = _datetime_to_text(value) if isinstance(value, datetime) else None
            assignments.append(f"{column_map[key]} = ?")
            values.append(value)

        if not assignments:
            return

        values.append(pipeline_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE data_pipelines SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )

    def create_farmer_action(self, action: FarmerAction) -> str:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO farmer_actions (
                    id, farm_id, action_type, summary, context, created_at, resolved_at, resolution
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action.id,
                    action.farm_id,
                    action.action_type,
                    action.summary,
                    _json_dumps(action.context),
                    _datetime_to_text(action.created_at),
                    _datetime_to_text(action.resolved_at) if action.resolved_at else None,
                    action.resolution,
                ),
            )
        self._record_system_activity(
            farm_id=action.farm_id,
            event_type="farmer_action",
            source="agent",
            occurred_at=action.created_at,
            title=action.summary,
            body=action.summary,
            payload={"action_id": action.id, "action_type": action.action_type, "context": action.context},
            targets=self._targets_from_context(action.farm_id, action.context),
            provenance={"source": "farmer_action", "action_id": action.id},
        )
        return action.id

    def list_pending_actions(self, farm_id: str) -> list[FarmerAction]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM farmer_actions
                WHERE farm_id = ? AND resolved_at IS NULL
                ORDER BY created_at ASC
                """,
                (farm_id,),
            ).fetchall()
        return [self._farmer_action_from_row(row) for row in rows]

    def resolve_farmer_action(self, action_id: str, resolution: str) -> None:
        existing_action = None
        for farm in self.list_farms():
            existing_action = next((action for action in self.list_pending_actions(farm.id) if action.id == action_id), None)
            if existing_action is not None:
                break
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE farmer_actions
                SET resolved_at = ?, resolution = ?
                WHERE id = ?
                """,
                (_datetime_to_text(datetime.utcnow()), resolution, action_id),
            )
        if existing_action is not None:
            self._record_system_activity(
                farm_id=existing_action.farm_id,
                event_type="farmer_action_resolved",
                source="agent",
                title=f"Action resolved: {existing_action.summary}",
                body=resolution,
                payload={"action_id": action_id, "resolution": resolution},
                targets=self._targets_from_context(existing_action.farm_id, existing_action.context),
                provenance={"source": "farmer_action", "action_id": action_id},
            )

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
        targets = [FarmActivityTarget(subject_type="farm", subject_id=plan.farm_id, relationship="farm")]
        if plan.herd_id:
            targets.append(FarmActivityTarget(subject_type="herd", subject_id=plan.herd_id))
        if plan.source_paddock_id:
            targets.extend(self._target_for_land_unit(plan.source_paddock_id, relationship="source"))
        if plan.target_paddock_id:
            targets.extend(self._target_for_land_unit(plan.target_paddock_id, relationship="target"))
        self._record_system_activity(
            farm_id=plan.farm_id,
            event_type="grazing_decision",
            source="movement_plan",
            occurred_at=plan.created_at,
            title=f"Grazing decision: {plan.action}",
            body="\n".join(plan.reasoning),
            payload={
                "plan_id": plan.id,
                "action": plan.action,
                "confidence": plan.confidence,
                "for_date": _date_to_text(plan.for_date),
                "source_paddock_id": plan.source_paddock_id,
                "target_paddock_id": plan.target_paddock_id,
                "status": plan.status,
            },
            targets=targets,
            provenance={"source": "movement_decision", "plan_id": plan.id},
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
        plan = self.get_plan(plan_id)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE movement_decisions
                SET status = ?, farmer_feedback = COALESCE(?, farmer_feedback)
                WHERE id = ?
                """,
                (status, feedback, plan_id),
            )
        if plan is not None:
            targets = [FarmActivityTarget(subject_type="farm", subject_id=plan.farm_id, relationship="farm")]
            if plan.herd_id:
                targets.append(FarmActivityTarget(subject_type="herd", subject_id=plan.herd_id))
            self._record_system_activity(
                farm_id=plan.farm_id,
                event_type="grazing_decision_status",
                source="movement_plan",
                title=f"Grazing decision {status}",
                body=feedback or "",
                payload={"plan_id": plan_id, "status": status, "feedback": feedback},
                targets=targets,
                provenance={"source": "movement_decision", "plan_id": plan_id},
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
        targets = [FarmActivityTarget(subject_type="farm", subject_id=brief.farm_id, relationship="farm")]
        if brief.recommendation.herd_id:
            targets.append(FarmActivityTarget(subject_type="herd", subject_id=brief.recommendation.herd_id))
        self._record_system_activity(
            farm_id=brief.farm_id,
            event_type="daily_brief",
            source="briefing",
            occurred_at=brief.generated_at,
            title="Daily brief generated",
            body=brief.summary,
            payload={
                "brief_id": brief.id,
                "recommendation_id": brief.recommendation.id,
                "uncertainty_request": brief.uncertainty_request,
                "highlights": brief.highlights,
            },
            targets=targets,
            provenance={"source": "daily_brief", "brief_id": brief.id},
        )
        return brief.id

    def get_daily_brief(self, brief_id: str) -> DailyBrief | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM daily_briefs WHERE id = ?",
                (brief_id,),
            ).fetchone()
        return None if row is None else self._daily_brief_from_row(row)
