"""Satellite-derived pasture observation pipeline."""

from __future__ import annotations

from openpasture.domain import Observation


class SatelliteObservationPipeline:
    """Produces observations from STAC-compatible imagery sources."""

    def collect(self, farm_id: str) -> list[Observation]:
        raise NotImplementedError("Satellite ingestion is not implemented yet.")
