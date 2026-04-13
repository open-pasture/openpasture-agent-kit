"""Data pipeline primitives for external farm system integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class DataPipeline:
    """A farm-specific recurring ingestion pipeline backed by an external service."""

    id: str
    farm_id: str
    name: str
    profile_id: str
    login_url: str
    target_urls: list[str]
    extraction_prompts: list[str]
    observation_source: str
    observation_tags: list[str] = field(default_factory=list)
    schedule: str = "0 5 * * *"
    vendor_skill_version: str | None = None
    enabled: bool = True
    last_collected_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
