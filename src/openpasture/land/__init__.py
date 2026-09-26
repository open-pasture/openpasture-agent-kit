"""Land connector: land reports from Alexandria, with offline and open-data fallbacks."""

from __future__ import annotations

import os

from .alexandria import AlexandriaLandSource
from .fixture import FixtureLandSource
from .open_data import OpenDataLandSource
from .service import LandReportService
from .source import LandSource

LAND_SOURCE_CHOICES = ("auto", "alexandria", "open_data", "fixture")


def land_source_from_env(choice: str | None = None) -> LandSource:
    """Pick a land source. ``auto`` uses Alexandria when FIRECRAWL_API_KEY is set."""

    selected = (choice or os.environ.get("OPENPASTURE_LAND_SOURCE") or "auto").strip().lower()
    if selected not in LAND_SOURCE_CHOICES:
        raise ValueError(f"Unsupported OPENPASTURE_LAND_SOURCE '{selected}'. Use one of: {', '.join(LAND_SOURCE_CHOICES)}.")
    if selected == "fixture":
        return FixtureLandSource()
    if selected == "open_data":
        return OpenDataLandSource()
    alexandria = AlexandriaLandSource.from_env()
    if alexandria is not None:
        return alexandria
    if selected == "alexandria":
        raise ValueError("OPENPASTURE_LAND_SOURCE=alexandria requires FIRECRAWL_API_KEY.")
    return OpenDataLandSource()


__all__ = [
    "AlexandriaLandSource",
    "FixtureLandSource",
    "LAND_SOURCE_CHOICES",
    "LandReportService",
    "LandSource",
    "OpenDataLandSource",
    "land_source_from_env",
]
