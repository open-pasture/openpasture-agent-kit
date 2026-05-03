"""Profile manifest assembly from the farm activity ledger."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from openpasture.domain import FarmActivityEvent
from openpasture.store.protocol import FarmStore


def _clean(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _clean(item) for key, item in asdict(value).items() if item is not None}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items() if item is not None}
    return value


def _profile_for_subject(store: FarmStore, farm_id: str, subject_type: str, subject_id: str) -> dict[str, object]:
    if subject_type == "farm":
        farm = store.get_farm(subject_id)
        return {"type": "farm", "id": subject_id, "record": _clean(farm) if farm else None}
    if subject_type in {"pasture", "paddock", "land_unit"}:
        unit = store.get_land_unit(subject_id)
        return {"type": subject_type, "id": subject_id, "record": _clean(unit) if unit else None}
    if subject_type == "herd":
        herd = next((item for item in store.get_herds(farm_id) if item.id == subject_id), None)
        return {"type": "herd", "id": subject_id, "record": _clean(herd) if herd else None}
    if subject_type == "animal":
        animal = store.get_animal(subject_id)
        return {"type": "animal", "id": subject_id, "record": _clean(animal) if animal else None}
    return {"type": subject_type, "id": subject_id, "record": None}


def _activity_digest(events: list[FarmActivityEvent]) -> dict[str, object]:
    counts = Counter(event.event_type for event in events)
    sources = Counter(event.source for event in events)
    most_recent = events[0] if events else None
    oldest = events[-1] if events else None
    return {
        "total": len(events),
        "by_type": dict(counts),
        "by_source": dict(sources),
        "most_recent_at": most_recent.occurred_at.isoformat() if most_recent else None,
        "oldest_at": oldest.occurred_at.isoformat() if oldest else None,
        "has_images": any(event.attachments for event in events),
        "has_health_events": any(event.event_type in {"health_check", "treatment"} for event in events),
        "has_breeding_events": any(event.event_type in {"breeding", "birth", "weaning"} for event in events),
    }


def _event_container(event: FarmActivityEvent) -> dict[str, object]:
    return {
        "type": event.event_type,
        "label": event.title,
        "first_at": event.occurred_at.isoformat(),
        "last_at": event.occurred_at.isoformat(),
        "source": event.source,
        "summary": event.summary,
        "targets": [_clean(target) for target in event.targets],
        "attachments": [_clean(attachment) for attachment in event.attachments],
        "activities": [
            {
                "at": event.occurred_at.isoformat(),
                "content": event.body or event.summary or event.title,
                "payload": _clean(event.payload),
                "provenance": _clean(event.provenance),
            }
        ],
    }


def build_profile_manifest(
    store: FarmStore,
    *,
    farm_id: str,
    subject_type: str,
    subject_id: str,
    limit: int = 50,
    before: str | None = None,
) -> dict[str, object]:
    """Build a facts-first profile manifest for a farm subject."""

    events = store.list_activity_feed(farm_id, subject_type, subject_id, limit=limit, before=before)
    profile = _profile_for_subject(store, farm_id, subject_type, subject_id)
    current_state = profile.get("record") or {}
    return {
        "type": "openpasture-profile-manifest",
        "generated_at": datetime.utcnow().isoformat(),
        "subject": {"type": subject_type, "id": subject_id, "farm_id": farm_id},
        "profile": profile,
        "current_state": current_state,
        "activity_digest": _activity_digest(events),
        "timeline": {"containers": [_event_container(event) for event in events]},
    }
