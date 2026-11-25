import pytest

from gobernar360.core.errors import ApiError
from gobernar360.platform.geo.geojson import (
    MAX_BOUNDARY_POSITIONS,
    MAX_LINE_POSITIONS,
    boundary_geometry,
    location_geometry,
)

SQUARE = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
BOTH = ("Point", "LineString")


def _error(call, *args) -> tuple[str, str]:
    with pytest.raises(ApiError) as caught:
        call(*args)
    assert caught.value.status_code == 422
    return caught.value.code, caught.value.message


def test_a_point_keeps_its_coordinates_and_loses_its_altitude_and_extra_members():
    geometry = {"type": "Point", "coordinates": [-62.3, -32.4, 110.5], "bbox": [0, 0, 1, 1]}

    assert location_geometry(geometry, BOTH) == {"type": "Point", "coordinates": [-62.3, -32.4]}


def test_a_line_keeps_its_points():
    geometry = {"type": "LineString", "coordinates": [[0, 0], [1, 1, 5], [2, 0]]}

    assert location_geometry(geometry, BOTH) == {
        "type": "LineString",
        "coordinates": [[0, 0], [1, 1], [2, 0]],
    }


@pytest.mark.parametrize(
    "coordinates", [[-180, -90], [180, 90], [0, 0]], ids=["least", "most", "zero"]
)
def test_the_edges_of_the_world_are_accepted(coordinates):
    geometry = {"type": "Point", "coordinates": coordinates}

    assert location_geometry(geometry, BOTH)["coordinates"] == coordinates


@pytest.mark.parametrize(
    "coordinates",
    [
        [180.0001, 0],
        [-180.0001, 0],
        [0, 90.0001],
        [0, -90.0001],
        [float("nan"), 0],
        [0, float("inf")],
        ["-62", "-32"],
        [True, False],
        [1],
        [1, 2, 3, 4],
        [],
        None,
        "1,2",
    ],
)
def test_impossible_points_are_refused(coordinates):
    assert _error(location_geometry, {"type": "Point", "coordinates": coordinates}, BOTH) == (
        "invalid_location",
        "The point needs a valid longitude and latitude.",
    )


@pytest.mark.parametrize("geometry", [None, [], "Point", {}, {"type": "Polygon"}, {"type": None}])
def test_only_the_accepted_kinds_are_locations(geometry):
    assert _error(location_geometry, geometry, BOTH) == (
        "invalid_location",
        "The location must be a GeoJSON Point or LineString.",
    )


def test_a_record_that_only_takes_points_refuses_a_line():
    geometry = {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}

    assert _error(location_geometry, geometry, ("Point",)) == (
        "invalid_location",
        "The location must be a GeoJSON Point.",
    )


@pytest.mark.parametrize("coordinates", [None, "x", [], [[0, 0]], [[1, 1], [1, 1]]])
def test_a_line_needs_two_different_points(coordinates):
    assert _error(location_geometry, {"type": "LineString", "coordinates": coordinates}, BOTH) == (
        "invalid_location",
        "The line needs at least two different points.",
    )


def test_every_point_of_a_line_must_be_possible_and_there_is_a_limit():
    bad = {"type": "LineString", "coordinates": [[0, 0], [200, 0]]}
    most = [[0, i / 1000] for i in range(MAX_LINE_POSITIONS)]

    assert _error(location_geometry, bad, BOTH) == (
        "invalid_location",
        "Every point of the line needs a valid longitude and latitude.",
    )
    assert location_geometry({"type": "LineString", "coordinates": most}, BOTH)
    longer = {"type": "LineString", "coordinates": [*most, [1, 1]]}
    assert _error(location_geometry, longer, BOTH)[0] == "invalid_location"


def test_a_polygon_becomes_a_multipolygon():
    assert boundary_geometry({"type": "Polygon", "coordinates": [SQUARE]}) == {
        "type": "MultiPolygon",
        "coordinates": [[SQUARE]],
    }


def test_a_multipolygon_keeps_its_parts_and_holes():
    hole = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.4], [0.2, 0.2]]
    other = [[[x + 5, y] for x, y in SQUARE]]
    geometry = {"type": "MultiPolygon", "coordinates": [[SQUARE, hole], other]}

    assert boundary_geometry(geometry)["coordinates"] == [[SQUARE, hole], other]


def test_an_open_boundary_is_refused():
    assert _error(boundary_geometry, {"type": "Polygon", "coordinates": [SQUARE[:-1]]}) == (
        "zone_not_closed",
        "The boundary is not closed: its last corner must be its first one.",
    )


@pytest.mark.parametrize(
    ("geometry", "message"),
    [
        (None, "The boundary must be a GeoJSON Polygon or MultiPolygon."),
        ({"type": "Point", "coordinates": [0, 0]}, "The boundary must be a GeoJSON Polygon or Mul"),
        ({"type": "Polygon", "coordinates": []}, "The boundary is empty."),
        ({"type": "MultiPolygon", "coordinates": []}, "The boundary is empty."),
        ({"type": "Polygon"}, "The boundary is empty."),
        ({"type": "MultiPolygon"}, "The boundary is empty."),
        ({"type": "MultiPolygon", "coordinates": 3}, "Every corner needs a valid"),
        ({"type": "MultiPolygon", "coordinates": [[]]}, "Every corner needs a valid"),
        ({"type": "Polygon", "coordinates": [3]}, "Every corner needs a valid"),
        ({"type": "Polygon", "coordinates": [[[0, 0], [200, 0], [1, 1], [0, 0]]]}, "Every corner"),
        (
            {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 0]]]},
            "The boundary needs at least three corners.",
        ),
    ],
)
def test_malformed_boundaries_are_refused(geometry, message):
    code, said = _error(boundary_geometry, geometry)

    assert code == "invalid_boundary"
    assert said.startswith(message)


def test_a_boundary_may_not_have_endless_corners():
    corners = [[i / MAX_BOUNDARY_POSITIONS, 0] for i in range(MAX_BOUNDARY_POSITIONS - 1)]
    most = {"type": "Polygon", "coordinates": [[*corners, corners[0]]]}
    more = {"type": "Polygon", "coordinates": [[*corners, [1, 1], corners[0]]]}

    assert boundary_geometry(most)
    assert _error(boundary_geometry, more) == (
        "invalid_boundary",
        "The boundary has more than 10000 corners.",
    )
