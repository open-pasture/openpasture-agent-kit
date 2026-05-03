"""Append-only activity primitives for farm profile history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


ACTIVITY_SUBJECT_TYPES = {"farm", "pasture", "paddock", "land_unit", "herd", "animal"}


@dataclass(slots=True)
class FarmActivityTarget:
    """A subject that should show an activity in its profile feed."""

    subject_type: str
    subject_id: str
    relationship: str = "primary"

    def __post_init__(self) -> None:
        if self.subject_type not in ACTIVITY_SUBJECT_TYPES:
            raise ValueError(f"Unsupported activity subject type: {self.subject_type}")


@dataclass(slots=True)
class FarmActivityAttachment:
    """Media or files attached to a historical activity."""

    id: str
    url: str
    media_type: str
    file_name: str | None = None
    content_type: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class FarmActivityEvent:
    """A durable historical fact relevant to one or more farm subjects."""

    id: str
    farm_id: str
    event_type: str
    source: str
    occurred_at: datetime
    title: str
    body: str = ""
    summary: str | None = None
    payload: dict[str, object] = field(default_factory=dict)
    provenance: dict[str, object] = field(default_factory=dict)
    targets: list[FarmActivityTarget] = field(default_factory=list)
    attachments: list[FarmActivityAttachment] = field(default_factory=list)
    visibility: str = "farm"
    recorded_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not any(target.subject_type == "farm" and target.subject_id == self.farm_id for target in self.targets):
            self.targets.insert(0, FarmActivityTarget(subject_type="farm", subject_id=self.farm_id, relationship="farm"))


@dataclass(slots=True)
class Animal:
    """An individual animal with current state kept separate from its activity history."""

    id: str
    farm_id: str
    species: str
    sex: str
    tag: str
    herd_id: str | None = None
    name: str | None = None
    secondary_tags: list[str] = field(default_factory=list)
    breed: str | None = None
    birth_date: str | None = None
    dam_id: str | None = None
    sire_id: str | None = None
    status: str = "active"
    current_paddock_id: str | None = None
    notes: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
