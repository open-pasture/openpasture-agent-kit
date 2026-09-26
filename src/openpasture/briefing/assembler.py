"""Morning brief assembly: the farmer-readable wrapper around the latest decision."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from openpasture.context import get_decision_engine, get_store
from openpasture.domain import DailyBrief
from openpasture.store.protocol import FarmStore

if TYPE_CHECKING:
    from openpasture.briefing.engine import DecisionEngine


class MorningBriefAssembler:
    """Runs (or reuses) this window's decision for a herd and wraps it as a brief."""

    def __init__(self, store: FarmStore | None = None, engine: DecisionEngine | None = None):
        self.store = store or get_store()
        self.engine = engine or get_decision_engine()

    def assemble(
        self,
        farm_id: str,
        for_date: date | None = None,
        *,
        herd_id: str | None = None,
        refresh: bool = False,
    ) -> DailyBrief:
        farm = self.store.get_farm(farm_id)
        if farm is None:
            raise ValueError(f"Farm '{farm_id}' does not exist.")
        now = self.engine.moment_for_date(farm, herd_id, for_date) if for_date is not None else None
        result, context = self.engine.run_cycle(farm_id, herd_id, now=now, force=refresh)
        return self.engine.build_brief(result.decision, context)
