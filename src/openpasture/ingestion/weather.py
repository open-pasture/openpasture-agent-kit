"""Weather observation pipeline."""

from __future__ import annotations

from openpasture.domain import Observation


class WeatherObservationPipeline:
    """Produces observations from forecast and historical weather APIs."""

    def collect(self, farm_id: str) -> list[Observation]:
        raise NotImplementedError("Weather ingestion is not implemented yet.")
