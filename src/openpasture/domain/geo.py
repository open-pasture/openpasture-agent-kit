"""Geospatial primitives used throughout the agent.

These types intentionally avoid any dependency on a GIS framework so they can be
shared by self-hosted and cloud-backed deployments alike.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GeoPoint:
    """A geographic point in longitude/latitude order."""

    longitude: float
    latitude: float


@dataclass(slots=True)
class GeoPolygon:
    """A simple polygon represented by an ordered ring of points."""

    coordinates: list[GeoPoint] = field(default_factory=list)


@dataclass(slots=True)
class BoundingBox:
    """A bounding box for quick spatial summaries and search hints."""

    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float
