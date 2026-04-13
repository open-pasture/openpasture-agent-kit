"""Farmer action primitives for agent-managed follow-up work."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class FarmerAction:
    """A request for the farmer to complete a specific unblocker."""

    id: str
    farm_id: str
    action_type: str
    summary: str
    context: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    resolution: str | None = None
