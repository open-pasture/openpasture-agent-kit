"""Planning and briefing primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

DecisionAction = Literal["MOVE", "STAY", "NEEDS_INFO"]


@dataclass(slots=True)
class MovementDecision:
    """A grazing recommendation for a specific decision window."""

    id: str
    farm_id: str
    for_date: date
    action: DecisionAction
    reasoning: list[str] = field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    source_paddock_id: str | None = None
    target_paddock_id: str | None = None
    knowledge_entry_ids: list[str] = field(default_factory=list)
    status: Literal["pending", "approved", "rejected", "modified"] = "pending"
    farmer_feedback: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class DailyBrief:
    """The human-readable morning briefing delivered to the farmer."""

    id: str
    farm_id: str
    generated_at: datetime
    summary: str
    recommendation: MovementDecision
    uncertainty_request: str | None = None
    highlights: list[str] = field(default_factory=list)
