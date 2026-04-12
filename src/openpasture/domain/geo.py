"""Geospatial primitives used throughout the agent.

These types intentionally avoid any dependency on a GIS framework so they can be
shared by self-hosted and cloud-backed deployments alike.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(slots=True)
class GeoPoint:
    """A geographic point in longitude/latitude order."""

    longitude: float
    latitude: float

    def to_geojson(self) -> dict[str, object]:
        """Return a GeoJSON Point mapping."""
        return {"type": "Point", "coordinates": [self.longitude, self.latitude]}

    @classmethod
    def from_geojson(cls, data: Mapping[str, object]) -> "GeoPoint":
        """Build a point from a GeoJSON Point mapping."""
        point_type = data.get("type")
        coordinates = data.get("coordinates")
        if point_type != "Point" or not isinstance(coordinates, list) or len(coordinates) != 2:
            raise ValueError("Invalid GeoJSON Point payload.")
        return cls(longitude=float(coordinates[0]), latitude=float(coordinates[1]))


@dataclass(slots=True)
class GeoPolygon:
    """A simple polygon represented by an ordered ring of points."""

    coordinates: list[GeoPoint] = field(default_factory=list)

    def _closed_ring(self) -> list[GeoPoint]:
        if not self.coordinates:
            return []
        ring = list(self.coordinates)
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        return ring

    def to_geojson(self) -> dict[str, object]:
        """Return a GeoJSON Polygon mapping."""
        return {
            "type": "Polygon",
            "coordinates": [
                [[point.longitude, point.latitude] for point in self._closed_ring()],
            ],
        }

    @classmethod
    def from_geojson(cls, data: Mapping[str, object]) -> "GeoPolygon":
        """Build a polygon from a GeoJSON Polygon mapping."""
        polygon_type = data.get("type")
        coordinates = data.get("coordinates")
        if polygon_type != "Polygon" or not isinstance(coordinates, list) or not coordinates:
            raise ValueError("Invalid GeoJSON Polygon payload.")

        outer_ring = coordinates[0]
        if not isinstance(outer_ring, list):
            raise ValueError("GeoJSON Polygon ring must be a list.")

        points: list[GeoPoint] = []
        for raw_point in outer_ring:
            if not isinstance(raw_point, list) or len(raw_point) != 2:
                raise ValueError("GeoJSON Polygon coordinates must be [longitude, latitude].")
            points.append(GeoPoint(longitude=float(raw_point[0]), latitude=float(raw_point[1])))

        if len(points) >= 2 and points[0] == points[-1]:
            points = points[:-1]

        return cls(coordinates=points)


@dataclass(slots=True)
class BoundingBox:
    """A bounding box for quick spatial summaries and search hints."""

    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float

    @classmethod
    def from_polygon(cls, polygon: GeoPolygon) -> "BoundingBox":
        """Compute a bounding box from a polygon."""
        if not polygon.coordinates:
            raise ValueError("Cannot build a bounding box from an empty polygon.")

        longitudes = [point.longitude for point in polygon.coordinates]
        latitudes = [point.latitude for point in polygon.coordinates]
        return cls(
            min_longitude=min(longitudes),
            min_latitude=min(latitudes),
            max_longitude=max(longitudes),
            max_latitude=max(latitudes),
        )
