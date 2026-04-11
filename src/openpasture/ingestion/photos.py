"""Photo-based observation pipeline."""

from __future__ import annotations

from openpasture.domain import Observation


class PhotoObservationPipeline:
    """Turns farmer photos into structured observations."""

    def analyze(self, farm_id: str, media_url: str) -> Observation:
        raise NotImplementedError("Photo analysis is not implemented yet.")
