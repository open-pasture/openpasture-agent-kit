"""Selects the next most useful observation request for the farmer."""

from __future__ import annotations

from openpasture.domain.observation import is_field_observation_source
from openpasture.context import get_store
from openpasture.store.protocol import FarmStore


class AttentionDirector:
    """Chooses the observation that would most reduce current uncertainty."""

    def __init__(self, store: FarmStore | None = None):
        self.store = store or get_store()

    def next_best_question(self, farm_id: str) -> str:
        observations = self.store.get_recent_observations(farm_id, days=7)
        field_observations = [obs for obs in observations if is_field_observation_source(obs.source)]
        weather_observations = [obs for obs in observations if obs.source == "weather"]
        latest_decision = self.store.get_latest_decision(farm_id)

        if not field_observations:
            return "What does the current paddock look like right now: pasture height, residual, and any muddy spots?"
        if weather_observations and not any("mud" in obs.content.lower() for obs in field_observations):
            return "After the recent weather, how firm is the ground and are animals starting to pug or stand around water?"
        if latest_decision and latest_decision.to_land_unit_id and latest_decision.status == "proposed":
            return "Before moving, how ready does the target paddock look in terms of regrowth and available feed?"
        return "If you were to check one thing right now, what are the animals telling you with their grazing behavior?"
