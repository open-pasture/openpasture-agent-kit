"""Selects the next most useful observation request for the farmer."""

from __future__ import annotations


class AttentionDirector:
    """Chooses the observation that would most reduce current uncertainty."""

    def next_best_question(self, farm_id: str) -> str:
        raise NotImplementedError("Attention direction is not implemented yet.")
