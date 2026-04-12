"""SQLite backend for the shared ancestral knowledge base."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from openpasture.domain import KnowledgeEntry, SourceRecord


def _json_dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def _datetime_to_text(value: datetime) -> str:
    return value.isoformat()


def _datetime_from_text(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _source_to_dict(source: SourceRecord) -> dict[str, object]:
    return {
        "source_url": source.source_url,
        "source_title": source.source_title,
        "source_author": source.source_author,
        "source_kind": source.source_kind,
        "segment": source.segment,
    }


def _source_from_dict(payload: dict[str, object]) -> SourceRecord:
    return SourceRecord(
        source_url=str(payload.get("source_url", "")),
        source_title=str(payload.get("source_title", "")),
        source_author=str(payload.get("source_author", "")),
        source_kind=str(payload.get("source_kind", "seed")),
        segment=str(payload["segment"]) if payload.get("segment") is not None else None,
    )


class SQLiteKnowledgeStore:
    """SQLite-backed implementation of the KnowledgeStore protocol."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "knowledge.db"
        self._fts_enabled = False

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
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_entries (
                    id TEXT PRIMARY KEY,
                    farm_id TEXT,
                    entry_type TEXT NOT NULL,
                    category TEXT,
                    content TEXT NOT NULL,
                    sources TEXT NOT NULL,
                    primary_author TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    embedding_id TEXT
                )
                """
            )

            try:
                connection.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                    USING fts5(
                        id UNINDEXED,
                        content,
                        category,
                        tags,
                        primary_author
                    )
                    """
                )
                self._fts_enabled = True
            except sqlite3.OperationalError:
                self._fts_enabled = False

    def _entry_from_row(self, row: sqlite3.Row) -> KnowledgeEntry:
        raw_sources = _json_loads(row["sources"], [])
        return KnowledgeEntry(
            id=row["id"],
            farm_id=row["farm_id"],
            entry_type=row["entry_type"],
            content=row["content"],
            sources=[
                _source_from_dict(source_payload)
                for source_payload in raw_sources
                if isinstance(source_payload, dict)
            ],
            created_at=_datetime_from_text(row["created_at"]),
            tags=[str(tag) for tag in _json_loads(row["tags"], [])],
            category=row["category"],
            embedding_id=row["embedding_id"],
        )

    def _matches_filters(
        self,
        entry: KnowledgeEntry,
        *,
        entry_types: list[str] | None = None,
        tags: list[str] | None = None,
        authors: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> bool:
        if entry_types and entry.entry_type not in set(entry_types):
            return False
        if categories and entry.category not in set(categories):
            return False
        if tags and not set(tags).issubset(set(entry.tags)):
            return False
        if authors and entry.primary_author not in set(authors):
            return False
        return True

    def _upsert_entry(self, connection: sqlite3.Connection, entry: KnowledgeEntry) -> None:
        primary_author = entry.primary_author
        connection.execute(
            """
            INSERT OR REPLACE INTO knowledge_entries (
                id, farm_id, entry_type, category, content, sources,
                primary_author, created_at, tags, embedding_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.farm_id,
                entry.entry_type,
                entry.category,
                entry.content,
                _json_dumps([_source_to_dict(source) for source in entry.sources]),
                primary_author,
                _datetime_to_text(entry.created_at),
                _json_dumps(entry.tags),
                entry.embedding_id,
            ),
        )
        if self._fts_enabled:
            connection.execute("DELETE FROM knowledge_fts WHERE id = ?", (entry.id,))
            connection.execute(
                """
                INSERT INTO knowledge_fts (id, content, category, tags, primary_author)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.content,
                    entry.category or "",
                    " ".join(entry.tags),
                    primary_author,
                ),
            )

    def store_entries(self, entries: list[KnowledgeEntry]) -> list[str]:
        ids: list[str] = []
        with self._connect() as connection:
            for entry in entries:
                self._upsert_entry(connection, entry)
                ids.append(entry.id)
        return ids

    def update_entry(self, entry: KnowledgeEntry) -> None:
        with self._connect() as connection:
            self._upsert_entry(connection, entry)

    def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_entries WHERE id = ?",
                (entry_id,),
            ).fetchone()
        return None if row is None else self._entry_from_row(row)

    def search(
        self,
        query: str,
        limit: int = 5,
        entry_types: list[str] | None = None,
        tags: list[str] | None = None,
        authors: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> list[KnowledgeEntry]:
        with self._connect() as connection:
            rows: list[sqlite3.Row] = []
            if self._fts_enabled:
                match_query = " ".join(part for part in query.split() if part) or query
                try:
                    rows = connection.execute(
                        """
                        SELECT ke.* FROM knowledge_fts fts
                        JOIN knowledge_entries ke ON ke.id = fts.id
                        WHERE knowledge_fts MATCH ?
                        LIMIT ?
                        """,
                        (match_query, max(limit * 5, limit)),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []

            if not rows:
                like_query = f"%{query.lower()}%"
                rows = connection.execute(
                    """
                    SELECT * FROM knowledge_entries
                    WHERE lower(content) LIKE ?
                       OR lower(tags) LIKE ?
                       OR lower(category) LIKE ?
                       OR lower(primary_author) LIKE ?
                    LIMIT ?
                    """,
                    (like_query, like_query, like_query, like_query, max(limit * 5, limit)),
                ).fetchall()

        entries = [self._entry_from_row(row) for row in rows]
        filtered = [
            entry
            for entry in entries
            if self._matches_filters(
                entry,
                entry_types=entry_types,
                tags=tags,
                authors=authors,
                categories=categories,
            )
        ]
        return filtered[:limit]

    def get_entries_by_author(self, author: str) -> list[KnowledgeEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM knowledge_entries
                WHERE primary_author = ?
                ORDER BY created_at DESC, id ASC
                """,
                (author,),
            ).fetchall()
        return [self._entry_from_row(row) for row in rows]

    def list_sources(self) -> list[SourceRecord]:
        seen: set[tuple[str, str, str, str, str | None]] = set()
        sources: list[SourceRecord] = []
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT sources FROM knowledge_entries ORDER BY created_at DESC, id ASC"
            ).fetchall()

        for row in rows:
            for payload in _json_loads(row["sources"], []):
                if not isinstance(payload, dict):
                    continue
                source = _source_from_dict(payload)
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
                sources.append(source)
        return sources

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM knowledge_entries").fetchone()
        return int(row["total"]) if row is not None else 0
