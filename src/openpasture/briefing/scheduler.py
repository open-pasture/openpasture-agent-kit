"""Scheduling helpers for recurring agent-driven workflows."""

from __future__ import annotations


class MorningBriefScheduler:
    """Schedules the recurring morning brief trigger for a farm."""

    def schedule(self, farm_id: str, timezone: str, hour: int = 5, minute: int = 30) -> None:
        raise NotImplementedError("Morning brief scheduling is not implemented yet.")
