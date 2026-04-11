"""Morning brief assembly logic."""

from __future__ import annotations

from openpasture.domain import DailyBrief


class MorningBriefAssembler:
    """Builds a daily brief from current farm context and relevant knowledge."""

    def assemble(self, farm_id: str) -> DailyBrief:
        raise NotImplementedError("Morning brief assembly is not implemented yet.")
