from openpasture.domain import BoundingBox, GeoFeature, GeoPoint, GeoPolygon


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


def test_geo_feature_normalizes_polygon_and_computes_metadata():
    feature = GeoFeature.from_geojson(
        {
            "type": "Feature",
            "properties": {"source": "map_screenshot"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-87.04, 35.64], [-87.03, 35.64], [-87.03, 35.63]]],
            },
        }
    )

    payload = feature.to_geojson()
    bbox = feature.bbox()

    assert payload["geometry"]["coordinates"][0][0] == payload["geometry"]["coordinates"][0][-1]
    assert bbox.to_list() == [-87.04, 35.63, -87.03, 35.64]
    assert feature.area_hectares() > 0
    assert feature.properties["source"] == "map_screenshot"
