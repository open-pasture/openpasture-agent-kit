"""Batch state management for reusable knowledge-ingestion runs."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utcnow() -> str:
    return datetime.utcnow().isoformat()


def _normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or default).strip()
    return text or default


class KnowledgeIngestionRunner:
    """Persists batch manifests for agent-driven knowledge ingestion."""

    TERMINAL_ITEM_STATUSES = {"completed", "failed", "skipped"}

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.batches_dir = self.data_dir / "knowledge-batches"
        self.batches_dir.mkdir(parents=True, exist_ok=True)

    def create_batch(
        self,
        *,
        batch_name: str,
        author: str,
        sources: list[dict[str, object]],
        source_kind: str = "web",
        notes: str | None = None,
    ) -> dict[str, Any]:
        batch_id = f"kbatch_{uuid4().hex[:12]}"
        now = _utcnow()
        items: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for index, source in enumerate(sources, start=1):
            url = _normalize_text(source.get("url"))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            item_source_kind = _normalize_text(source.get("source_kind"), default=source_kind)
            items.append(
                {
                    "url": url,
                    "source_title": _normalize_text(source.get("source_title"), default=url),
                    "source_kind": item_source_kind,
                    "status": "pending",
                    "reason": None,
                    "queued_at": None,
                    "claimed_at": None,
                    "completed_at": None,
                    "attempts": 0,
                    "result": {
                        "stored_count": 0,
                        "updated_count": 0,
                        "entry_ids": [],
                        "note": None,
                        "error": None,
                    },
                    "order": index,
                }
            )

        batch = {
            "id": batch_id,
            "batch_name": batch_name.strip(),
            "author": author.strip(),
            "source_kind": source_kind.strip() or "web",
            "notes": notes.strip() if notes else None,
            "created_at": now,
            "updated_at": now,
            "status": "pending",
            "items": items,
        }
        self._save_batch(batch)
        return self.get_batch(batch_id)

    def get_batch(self, batch_id: str) -> dict[str, Any]:
        batch = self._load_batch(batch_id)
        return self._with_summary(batch)

    def mark_item_queued(
        self,
        batch_id: str,
        *,
        url: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        batch = self._load_batch(batch_id)
        item = self._find_item(batch, url)
        item["status"] = "queued" if reason is None else "skipped"
        item["reason"] = reason
        item["queued_at"] = _utcnow() if reason is None else item.get("queued_at")
        item["claimed_at"] = None
        item["completed_at"] = _utcnow() if reason is not None else None
        self._save_batch(batch)
        return self._with_summary(batch)

    def claim_item(self, batch_id: str, *, url: str) -> dict[str, Any]:
        batch = self._load_batch(batch_id)
        item = self._find_item(batch, url)
        item["status"] = "claimed"
        item["claimed_at"] = _utcnow()
        item["attempts"] = int(item.get("attempts", 0)) + 1
        self._save_batch(batch)
        return item

    def record_result(
        self,
        batch_id: str,
        *,
        url: str,
        status: str,
        stored_count: int = 0,
        updated_count: int = 0,
        entry_ids: list[str] | None = None,
        note: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        batch = self._load_batch(batch_id)
        item = self._find_item(batch, url)
        item["status"] = status
        item["completed_at"] = _utcnow()
        item["reason"] = error if status == "failed" else item.get("reason")
        item["result"] = {
            "stored_count": max(0, int(stored_count)),
            "updated_count": max(0, int(updated_count)),
            "entry_ids": sorted({str(entry_id) for entry_id in (entry_ids or []) if str(entry_id).strip()}),
            "note": note.strip() if note else None,
            "error": error.strip() if error else None,
        }
        self._save_batch(batch)
        return self._with_summary(batch)

    def next_pending_item(self, batch_id: str) -> dict[str, Any] | None:
        batch = self._load_batch(batch_id)
        for item in batch["items"]:
            if item["status"] in {"queued", "claimed", "pending"}:
                return item
        return None

    def _batch_path(self, batch_id: str) -> Path:
        return self.batches_dir / f"{batch_id}.json"

    def _load_batch(self, batch_id: str) -> dict[str, Any]:
        path = self._batch_path(batch_id)
        if not path.exists():
            raise ValueError(f"Knowledge ingestion batch '{batch_id}' does not exist.")
        return json.loads(path.read_text())

    def _save_batch(self, batch: dict[str, Any]) -> None:
        batch["updated_at"] = _utcnow()
        batch["status"] = self._derive_batch_status(batch["items"])
        path = self._batch_path(str(batch["id"]))
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(batch, indent=2, sort_keys=True))
        temp_path.replace(path)

    def _find_item(self, batch: dict[str, Any], url: str) -> dict[str, Any]:
        normalized_url = url.strip()
        for item in batch["items"]:
            if str(item.get("url", "")).strip() == normalized_url:
                return item
        raise ValueError(f"Source '{url}' is not part of batch '{batch['id']}'.")

    def _derive_batch_status(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return "empty"
        counts = Counter(str(item.get("status", "pending")) for item in items)
        if counts["claimed"]:
            return "running"
        if counts["queued"]:
            return "queued"
        if counts["pending"] == len(items):
            return "pending"
        if counts["failed"] and counts["failed"] + counts["completed"] + counts["skipped"] == len(items):
            return "completed_with_failures"
        if counts["completed"] + counts["skipped"] == len(items):
            return "completed"
        return "running"

    def _with_summary(self, batch: dict[str, Any]) -> dict[str, Any]:
        items = list(batch.get("items", []))
        counts = Counter(str(item.get("status", "pending")) for item in items)
        stored_total = 0
        updated_total = 0
        entry_ids: set[str] = set()

        for item in items:
            result = item.get("result", {})
            if not isinstance(result, dict):
                continue
            stored_total += int(result.get("stored_count", 0) or 0)
            updated_total += int(result.get("updated_count", 0) or 0)
            for entry_id in result.get("entry_ids", []):
                entry_ids.add(str(entry_id))

        summary = {
            "requested_sources": len(items),
            "queued_sources": counts["queued"],
            "claimed_sources": counts["claimed"],
            "completed_sources": counts["completed"],
            "failed_sources": counts["failed"],
            "skipped_sources": counts["skipped"],
            "pending_sources": counts["pending"],
            "stored_lessons": stored_total,
            "updated_lessons": updated_total,
            "entry_ids": sorted(entry_ids),
        }
        payload = dict(batch)
        payload["status"] = self._derive_batch_status(items)
        payload["summary"] = summary
        return payload
