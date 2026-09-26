"""Satellite-derived pasture observation pipeline."""

from __future__ import annotations

from openpasture.domain import Observation


class SatelliteObservationPipeline:
    """Produces observations from STAC-compatible imagery sources.

    Without Alexandria, this is the fallback for the land report ``imagery``
    section. Direct STAC ingestion is not implemented yet, so the section comes
    back unavailable with that reason.
    """

    def collect(self, farm_id: str) -> list[Observation]:
        raise NotImplementedError("Satellite ingestion is not implemented yet.")

    def fetch_section(self, geometry: dict[str, object], options: dict[str, object]) -> dict[str, object]:
        """Return a contract-shaped imagery section. Raises until STAC ingestion lands."""

        del geometry, options
        raise NotImplementedError(
            "Direct satellite ingestion is not implemented yet. Configure Alexandria for imagery."
        )
