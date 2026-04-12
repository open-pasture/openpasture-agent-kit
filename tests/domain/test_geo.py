from openpasture.domain import BoundingBox, GeoPoint, GeoPolygon


def test_geo_point_round_trip_geojson():
    point = GeoPoint(longitude=-95.123, latitude=36.456)

    payload = point.to_geojson()
    restored = GeoPoint.from_geojson(payload)

    assert payload == {"type": "Point", "coordinates": [-95.123, 36.456]}
    assert restored == point


def test_geo_polygon_round_trip_geojson_and_bbox():
    polygon = GeoPolygon(
        coordinates=[
            GeoPoint(longitude=-95.0, latitude=36.0),
            GeoPoint(longitude=-95.1, latitude=36.0),
            GeoPoint(longitude=-95.1, latitude=36.1),
        ]
    )

    payload = polygon.to_geojson()
    restored = GeoPolygon.from_geojson(payload)
    bbox = BoundingBox.from_polygon(restored)

    assert payload["type"] == "Polygon"
    assert restored.coordinates == polygon.coordinates
    assert bbox.min_longitude == -95.1
    assert bbox.max_latitude == 36.1
