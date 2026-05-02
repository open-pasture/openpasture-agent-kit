"""Geospatial primitives used throughout the agent.

These types intentionally avoid any dependency on a GIS framework so they can be
shared by self-hosted and cloud-backed deployments alike.
"""

from __future__ import annotations

import math
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


def _ensure_number_pair(raw_point: object) -> list[float]:
    if not isinstance(raw_point, (list, tuple)) or len(raw_point) < 2:
        raise ValueError("GeoJSON coordinates must be [longitude, latitude].")
    longitude = float(raw_point[0])
    latitude = float(raw_point[1])
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")
    return [longitude, latitude]


def _close_ring(raw_ring: object) -> list[list[float]]:
    if not isinstance(raw_ring, list):
        raise ValueError("GeoJSON polygon rings must be arrays.")
    ring = [_ensure_number_pair(point) for point in raw_ring]
    if len(ring) < 3:
        raise ValueError("A polygon ring needs at least three distinct points.")
    if ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    if len(ring) < 4:
        raise ValueError("A closed polygon ring needs at least four coordinates.")
    return ring


def _normalize_polygon_coordinates(raw_coordinates: object) -> list[list[list[float]]]:
    if not isinstance(raw_coordinates, list) or not raw_coordinates:
        raise ValueError("Polygon coordinates must contain at least one ring.")
    return [_close_ring(ring) for ring in raw_coordinates]


def _iter_positions(geometry: Mapping[str, object]) -> list[list[float]]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    positions: list[list[float]] = []
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        for ring in coordinates:
            if isinstance(ring, list):
                positions.extend(_ensure_number_pair(point) for point in ring)
    elif geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        for polygon in coordinates:
            if isinstance(polygon, list):
                for ring in polygon:
                    if isinstance(ring, list):
                        positions.extend(_ensure_number_pair(point) for point in ring)
    return positions


def _ring_area_square_meters(ring: list[list[float]]) -> float:
    """Approximate geodesic area for a small lon/lat ring."""

    if len(ring) < 4:
        return 0.0
    mean_latitude = math.radians(sum(point[1] for point in ring[:-1]) / (len(ring) - 1))
    meters_per_degree_latitude = 111_320.0
    meters_per_degree_longitude = meters_per_degree_latitude * math.cos(mean_latitude)
    origin_longitude = ring[0][0]
    origin_latitude = ring[0][1]
    projected = [
        (
            (point[0] - origin_longitude) * meters_per_degree_longitude,
            (point[1] - origin_latitude) * meters_per_degree_latitude,
        )
        for point in ring
    ]
    signed_area = 0.0
    for idx, (x1, y1) in enumerate(projected[:-1]):
        x2, y2 = projected[idx + 1]
        signed_area += x1 * y2 - x2 * y1
    return abs(signed_area) / 2.0


@dataclass(slots=True)
class GeoFeature:
    """A normalized GeoJSON Feature for farm land-unit boundaries."""

    geometry: dict[str, object]
    properties: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_geojson(cls, data: Mapping[str, object]) -> "GeoFeature":
        """Build a normalized Polygon/MultiPolygon feature from GeoJSON."""

        if data.get("type") == "Feature":
            raw_geometry = data.get("geometry")
            raw_properties = data.get("properties")
            if not isinstance(raw_geometry, Mapping):
                raise ValueError("GeoJSON Feature must include a geometry object.")
            properties = dict(raw_properties) if isinstance(raw_properties, Mapping) else {}
        else:
            raw_geometry = data
            properties = {}

        geometry_type = raw_geometry.get("type")
        coordinates = raw_geometry.get("coordinates")
        if geometry_type == "Polygon":
            geometry = {
                "type": "Polygon",
                "coordinates": _normalize_polygon_coordinates(coordinates),
            }
        elif geometry_type == "MultiPolygon":
            if not isinstance(coordinates, list) or not coordinates:
                raise ValueError("MultiPolygon coordinates must contain at least one polygon.")
            geometry = {
                "type": "MultiPolygon",
                "coordinates": [_normalize_polygon_coordinates(polygon) for polygon in coordinates],
            }
        else:
            raise ValueError("Land-unit geometry must be a GeoJSON Polygon or MultiPolygon.")

        return cls(geometry=geometry, properties=properties)

    def to_geojson(self) -> dict[str, object]:
        """Return a GeoJSON Feature mapping."""

        return {
            "type": "Feature",
            "properties": dict(self.properties),
            "geometry": self.geometry,
        }

    def bbox(self) -> "BoundingBox":
        """Compute the feature's bounding box."""

        positions = _iter_positions(self.geometry)
        if not positions:
            raise ValueError("Cannot compute a bounding box from empty geometry.")
        return BoundingBox(
            min_longitude=min(point[0] for point in positions),
            min_latitude=min(point[1] for point in positions),
            max_longitude=max(point[0] for point in positions),
            max_latitude=max(point[1] for point in positions),
        )

    def centroid(self) -> GeoPoint:
        """Return a simple centroid suitable for map focus and search hints."""

        positions = _iter_positions(self.geometry)
        if not positions:
            raise ValueError("Cannot compute a centroid from empty geometry.")
        return GeoPoint(
            longitude=sum(point[0] for point in positions) / len(positions),
            latitude=sum(point[1] for point in positions) / len(positions),
        )

    def area_hectares(self) -> float:
        """Approximate the feature area in hectares."""

        total_square_meters = 0.0
        geometry_type = self.geometry.get("type")
        coordinates = self.geometry.get("coordinates")
        polygons = coordinates if geometry_type == "MultiPolygon" else [coordinates]
        if not isinstance(polygons, list):
            return 0.0
        for polygon in polygons:
            if not isinstance(polygon, list) or not polygon:
                continue
            outer = polygon[0]
            if isinstance(outer, list):
                total_square_meters += _ring_area_square_meters(outer)
        return round(total_square_meters / 10_000, 4)

    def contains_bbox(self, other: "GeoFeature") -> bool:
        """Return True when this feature's bbox fully contains the other bbox."""

        outer = self.bbox()
        inner = other.bbox()
        return (
            outer.min_longitude <= inner.min_longitude
            and outer.min_latitude <= inner.min_latitude
            and outer.max_longitude >= inner.max_longitude
            and outer.max_latitude >= inner.max_latitude
        )

    def to_polygon(self) -> GeoPolygon | None:
        """Return a legacy GeoPolygon when the feature is a simple Polygon."""

        if self.geometry.get("type") != "Polygon":
            return None
        coordinates = self.geometry.get("coordinates")
        if not isinstance(coordinates, list):
            return None
        return GeoPolygon.from_geojson({"type": "Polygon", "coordinates": coordinates})


@dataclass(slots=True)
class BoundingBox:
    """A bounding box for quick spatial summaries and search hints."""

    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float

    def to_list(self) -> list[float]:
        """Return [west, south, east, north]."""

        return [self.min_longitude, self.min_latitude, self.max_longitude, self.max_latitude]

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
