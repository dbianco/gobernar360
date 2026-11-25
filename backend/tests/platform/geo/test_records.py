"""Maps, the review list and locations, through the API."""

import pytest

from gobernar360.platform.geo import features
from tests.economic.factories import make_actor_type, make_sector
from tests.factories import login, make_membership, make_municipality, make_user
from tests.platform.geo.factories import (
    at,
    line,
    make_actor_at,
    make_zone,
    point,
    signed_in_admin,
    square,
)
from tests.platform.geo.test_assignment import make_project_at

ACTORS = "/api/dashboards/economic/geo/actors"
PROJECTS = "/api/dashboards/projects/geo/projects"
STREETS = features.FIRST_UNCLUSTERED_ZOOM


def box(x: float, y: float, width: float = 1) -> str:
    west, south = at(x, y)
    east, north = at(x + width, y + width)
    return f"{west},{south},{east},{north}"


def _features(client, bbox, zoom=STREETS, base=ACTORS, **params):
    response = client.get(f"{base}/features", params={"bbox": bbox, "zoom": zoom} | params)
    assert response.status_code == 200, response.text
    return response.json()


def _titles(found) -> list[str]:
    return [feature["title"] for feature in found["features"]]


def _error(response) -> tuple[int, str, str]:
    error = response.json()["error"]
    return response.status_code, error["code"], error["message"]


def test_the_map_gets_only_what_is_inside_the_visible_area(client):
    municipality = signed_in_admin(client)
    inside = make_actor_at(municipality, "Adentro", point(0.5, 0.5))
    make_actor_at(municipality, "Borde", point(1, 1))
    for name, x, y in (("E", 1.01, 0.5), ("O", -0.01, 0.5), ("N", 0.5, 1.01), ("S", 0.5, -0.01)):
        make_actor_at(municipality, name, point(x, y))
    make_actor_at(municipality, "Sin lugar", None)

    found = _features(client, box(0, 0))

    assert found == {
        "restricted": False,
        "total": 2,
        "features": [
            {"id": str(inside.id), "title": "Adentro", "geometry": point(0.5, 0.5)},
            found["features"][1],
        ],
        "clusters": [],
        "truncated": False,
    }
    assert _titles(found) == ["Adentro", "Borde"]
    assert _titles(_features(client, box(1, 0))) == ["Borde", "E"]


@pytest.mark.parametrize("zoom", [0, 5, 12, 16, 17, 22])
def test_no_zoom_lets_records_outside_the_area_in(client, zoom):
    municipality = signed_in_admin(client)
    for index in range(6):
        make_actor_at(municipality, f"Adentro {index}", point(0.1 + index / 10, 0.5))
        make_actor_at(municipality, f"Afuera {index}", point(1.1 + index / 10, 0.5))

    found = _features(client, box(0, 0), zoom)

    shown = len(found["features"]) + sum(c["count"] for c in found["clusters"])
    assert (found["total"], shown) == (6, 6)
    assert all(title.startswith("Adentro") for title in _titles(found))
    for cluster in found["clusters"]:
        assert at(0, 0)[0] <= cluster["center"][0] <= at(1, 0)[0]


def test_records_cluster_when_zooming_out_and_separate_when_zooming_in(client):
    municipality = signed_in_admin(client)
    for index in range(3):
        make_actor_at(municipality, f"Cerca {index}", point(0.1 + index / 5, 0.1))
    far = make_actor_at(municipality, "Lejos", point(40, 40))
    world = "-180,-90,180,90"

    out = _features(client, world, 10)
    closest = _features(client, world, 16)

    assert [c["count"] for c in out["clusters"]] == [3]
    [cluster] = out["clusters"]
    assert cluster["center"] == pytest.approx(at(0.3, 0.1), abs=1e-6)
    assert cluster["bounds"] == pytest.approx([*at(0.1, 0.1), *at(0.5, 0.1)], abs=1e-6)
    # One alone in its square is the record itself.
    assert out["features"] == [{"id": str(far.id), "title": "Lejos", "geometry": point(40, 40)}]
    assert out["total"] == closest["total"] == 4
    assert closest["clusters"] == []
    assert _titles(closest) == ["Cerca 0", "Cerca 1", "Cerca 2", "Lejos"]
    assert [c["count"] for c in _features(client, world, 0)["clusters"]] == [4]


def test_clusters_do_not_change_while_panning(client):
    municipality = signed_in_admin(client)
    for index in range(20):
        make_actor_at(municipality, f"A{index}", point(0.3 + index * 0.02, 0.5))

    clusters = [
        _features(client, box(start, 0, 1), 14)["clusters"] for start in (-0.1, 0, 0.05, 0.2)
    ]

    assert clusters[0] and all(found == clusters[0] for found in clusters)


def test_records_at_the_same_place_are_all_sent_at_street_level(client):
    municipality = signed_in_admin(client)
    for name in ("Galería 1", "Galería 2"):
        make_actor_at(municipality, name, point(0.5, 0.5))

    assert _titles(_features(client, box(0, 0), 16)) == []
    assert _titles(_features(client, box(0, 0), STREETS)) == ["Galería 1", "Galería 2"]


def test_the_map_says_when_it_is_not_showing_everything(client, monkeypatch):
    municipality = signed_in_admin(client)
    monkeypatch.setattr(features, "MAX_FEATURES", 2)
    for name in ("A", "B"):
        make_actor_at(municipality, name, point(0.5, 0.5))
    assert _features(client, box(0, 0))["truncated"] is False

    make_actor_at(municipality, "C", point(0.5, 0.5))
    found = _features(client, box(0, 0))

    assert (found["truncated"], found["total"], _titles(found)) == (True, 3, ["A", "B"])


def test_a_line_is_on_the_map_when_it_enters_the_area_and_not_when_only_its_box_does(client):
    municipality = signed_in_admin(client)
    diagonal = line((0, 0), (2, 2))
    make_project_at(municipality, diagonal, "Calle")

    # A corner of the line's box, far from the line.
    assert _features(client, box(1.5, 0, 0.4), base=PROJECTS)["total"] == 0
    [feature] = _features(client, box(0.5, 0.5), base=PROJECTS)["features"]
    assert feature["geometry"] == diagonal


def test_the_map_takes_the_filters_of_the_list(client):
    municipality = signed_in_admin(client)
    kind, sector = make_actor_type(municipality), make_sector(municipality)
    make_actor_at(municipality, "Panadería Ñandú", point(0.5, 0.5), sector_id=sector.id)
    make_actor_at(
        municipality, "Taller", point(0.5, 0.5), actor_type_id=kind.id, cuit="30712345678"
    )

    def titles(**params):
        listed = client.get("/api/dashboards/economic/actors", params=params).json()["items"]
        shown = _titles(_features(client, box(0, 0), **params))
        assert shown == [actor["name"] for actor in listed]
        return shown

    assert titles(q="nandu") == ["Panadería Ñandú"]
    assert titles(q="30-7123") == ["Taller"]
    assert titles(sector_id=str(sector.id)) == ["Panadería Ñandú"]
    assert titles(actor_type_id=str(kind.id)) == ["Taller"]
    assert titles(actor_type_id=str(kind.id), q="pan") == []
    # As the screens send a filter left empty.
    assert len(_titles(_features(client, box(0, 0), q="", sector_id=""))) == 2
    assert len(titles(q="  ")) == 2


def test_project_filters_include_the_status_worked_out_from_dates(client):
    municipality = signed_in_admin(client)
    project = make_project_at(municipality, point(0.5, 0.5), "Plaza")
    client.patch(
        f"/api/dashboards/projects/projects/{project.id}",
        json={"status": "in_progress", "end_date": "2024-01-01"},
    )

    def total(**params):
        return _features(client, box(0, 0), base=PROJECTS, **params)["total"]

    assert (total(status="delayed"), total(status="in_progress")) == (1, 0)
    assert (total(year=project.year), total(year=project.year + 1)) == (1, 0)
    assert (total(term_id=str(project.term_id)), total(axis_id=str(project.term_id))) == (1, 0)
    assert (total(q="plaza"), total(q="calle"), total(priority="C")) == (1, 0, 0)


@pytest.mark.parametrize(
    "bbox",
    ["", "1,2,3", "1,2,3,4,5", "a,b,c,d", "nan,0,1,1", "0,0,0,1", "0,1,1,1", "1,0,0,1",
     "-181,0,1,1", "0,-91,1,1", "0,0,181,1", "0,0,1,91", "0,nan,1,1"],
)  # fmt: skip
def test_an_impossible_area_is_refused(client, bbox):
    signed_in_admin(client)

    response = client.get(f"{ACTORS}/features", params={"bbox": bbox, "zoom": 10})

    status, code, message = _error(response)
    assert (status, code) == (422, "invalid_area")
    assert message.startswith("The area must be")


def test_zoom_and_filters_are_checked(client):
    signed_in_admin(client)
    area = box(0, 0)

    for params in ({"zoom": -1}, {"zoom": 23}, {"zoom": 10, "sector_id": "x"}, {}):
        response = client.get(f"{ACTORS}/features", params={"bbox": area} | params)
        assert _error(response)[:2] == (422, "validation_error"), params
    response = client.get(f"{ACTORS}/features", params={"bbox": area, "zoom": 1, "sector_id": "x"})
    [detail] = response.json()["error"]["details"]
    assert detail["field"] == "sector_id"
    assert client.get(f"{ACTORS}/zones", params={"sector_id": "x"}).status_code == 422
    assert client.get(f"{ACTORS}/zones", params={"q": "x" * 101}).status_code == 422


# Locations


def test_editor_sets_a_location_and_viewer_reads_it(client):
    municipality = make_municipality()
    zone = make_zone(municipality)
    actor = make_actor_at(municipality, "Taller", None)
    for email, level in (("carla@noetinger.test", "editor"), ("leo@noetinger.test", "viewer")):
        make_membership(make_user(email), municipality, grants={"economic": level})
    path = f"{ACTORS}/{actor.id}/location"
    login(client, "carla@noetinger.test")

    saved = client.put(path, json={"location": point(0.5, 0.5)})
    client.post("/api/auth/logout")
    login(client, "leo@noetinger.test")

    assert (
        saved.json()
        == client.get(path).json()
        == {
            "location": point(0.5, 0.5),
            "kinds": ["Point"],
            "zones": [{"id": str(zone.id), "name": "Centro"}],
        }
    )
    assert client.put(path, json={"location": None}).status_code == 403
    assert client.get(path).json()["location"] == point(0.5, 0.5)


def test_a_project_takes_a_point_or_a_line_and_an_actor_only_a_point(client):
    municipality = signed_in_admin(client)
    project = make_project_at(municipality, None)
    actor = make_actor_at(municipality, "Taller", None)
    street = line((0, 0), (1, 1))

    assert client.get(f"{PROJECTS}/{project.id}/location").json()["kinds"] == [
        "Point",
        "LineString",
    ]
    for location in (street, point(1, 1)):
        response = client.put(f"{PROJECTS}/{project.id}/location", json={"location": location})
        assert response.json()["location"] == location
    refused = client.put(f"{ACTORS}/{actor.id}/location", json={"location": street})
    assert _error(refused) == (422, "invalid_location", "The location must be a GeoJSON Point.")
    refused = client.put(f"{PROJECTS}/{project.id}/location", json={"location": square(0, 0)})
    assert _error(refused)[:2] == (422, "invalid_location")
    assert client.put(f"{ACTORS}/{actor.id}/location", json={}).status_code == 422
    assert (
        client.put(f"{ACTORS}/{actor.id}/location", json={"location": None, "x": 1}).status_code
        == 422
    )


def test_dashboards_and_records_that_do_not_exist(client):
    municipality = signed_in_admin(client, "economic")
    actor = make_actor_at(municipality, "Taller", None)
    missing = "00000000-0000-0000-0000-000000000000"

    # Not enabled here and not installed are answered the same way.
    assert client.get(f"{PROJECTS}/zones").status_code == 403
    assert client.get("/api/dashboards/nope/geo/actors/zones").status_code == 403
    assert client.get("/api/dashboards/economic/geo/people/zones").status_code == 404
    assert client.get(f"{ACTORS}/{missing}/location").status_code == 404
    assert client.put(f"{ACTORS}/{missing}/location", json={"location": None}).status_code == 404
    assert client.get(f"{ACTORS}/{actor.id}/location").status_code == 200


# Review list


def test_records_outside_every_zone_are_listed_for_review(client):
    municipality = signed_in_admin(client)
    make_zone(municipality)
    make_actor_at(municipality, "Adentro", point(0.5, 0.5))
    ambar = make_actor_at(municipality, "Ámbar", point(5, 5))
    make_actor_at(municipality, "Zinc", point(5, 5))
    make_actor_at(municipality, "Sin lugar", None)

    outside = client.get(f"{ACTORS}/unzoned").json()
    unlocated = client.get(f"{ACTORS}/unzoned", params={"reason": "unlocated"}).json()

    assert [item["title"] for item in outside["items"]] == ["Ámbar", "Zinc"]
    assert outside["total"] == 2
    assert outside["items"][0] == {"id": str(ambar.id), "title": "Ámbar"}
    assert [item["title"] for item in unlocated["items"]] == ["Sin lugar"]
    page = client.get(f"{ACTORS}/unzoned", params={"limit": 1, "offset": 1}).json()
    assert ([item["title"] for item in page["items"]], page["total"]) == (["Zinc"], 2)
    found = client.get(f"{ACTORS}/unzoned", params={"q": "ambar"}).json()
    assert ([item["title"] for item in found["items"]], found["total"]) == (["Ámbar"], 1)
    assert client.get(f"{ACTORS}/unzoned", params={"reason": "x"}).status_code == 422


def test_a_project_moved_outside_every_zone_shows_up_for_review(client):
    municipality = signed_in_admin(client)
    make_zone(municipality)
    project = make_project_at(municipality, point(0.5, 0.5))
    assert client.get(f"{PROJECTS}/unzoned").json()["total"] == 0

    client.put(f"{PROJECTS}/{project.id}/location", json={"location": point(7, 7)})

    assert client.get(f"{PROJECTS}/unzoned").json()["items"] == [
        {"id": str(project.id), "title": "Pavimento"}
    ]


# CSV


def test_exports_carry_the_zone_and_the_coordinates(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Centro", square(0, 0))
    make_zone(municipality, "=Este", square(1, 0))
    make_actor_at(municipality, "Taller", point(0.5, 0.25))
    make_project_at(municipality, line((0.5, 0.5), (1, 0.5), (1.5, 0.5)))

    actors = client.get("/api/dashboards/economic/export/actors.csv").text.splitlines()
    projects = client.get("/api/dashboards/projects/export/projects.csv").text.splitlines()

    longitude, latitude = at(0.5, 0.25)
    assert actors[1].endswith(f"Centro,{latitude},{longitude}")
    # Of a line, a point on it. Zones come by name, and spreadsheets must not run them.
    assert projects[0].endswith("zones,latitude,longitude")
    assert projects[1].endswith(f"'=Este;Centro,{at(1, 0.5)[1]},{at(1, 0.5)[0]}")


# Isolation


def test_two_municipalities_with_overlapping_places_never_see_each_other(client):
    noetinger, saira = signed_in_admin(client), make_municipality("Saira")
    for municipality in (noetinger, saira):
        make_zone(municipality, f"Zona de {municipality.name}", square(0, 0))
        make_actor_at(municipality, f"Taller de {municipality.name}", point(0.5, 0.5))
        make_actor_at(municipality, f"Campo de {municipality.name}", point(5, 5))
    theirs = make_actor_at(saira, "Ajeno", point(0.5, 0.5))

    for zoom in (0, 10, STREETS):
        assert _features(client, "-180,-90,180,90", zoom)["total"] == 2
    assert _titles(_features(client, box(0, 0))) == ["Taller de Noetinger"]
    breakdown = client.get(f"{ACTORS}/zones").json()
    assert [(r["zone"]["name"], r["values"]) for r in breakdown["zones"]] == [
        ("Zona de Noetinger", {"actors": 1})
    ]
    assert (breakdown["outside"]["values"], breakdown["total"]["values"]) == (
        {"actors": 1},
        {"actors": 2},
    )
    unzoned = client.get(f"{ACTORS}/unzoned").json()
    assert [item["title"] for item in unzoned["items"]] == ["Campo de Noetinger"]
    path = f"{ACTORS}/{theirs.id}/location"
    assert client.get(path).status_code == 404
    assert client.put(path, json={"location": point(9, 9)}).status_code == 404
    assert "Saira" not in client.get(f"{ACTORS}/zones.csv").text


def test_records_with_the_same_name_always_come_in_the_same_order(client):
    municipality = signed_in_admin(client)
    made = [make_actor_at(municipality, "Igual", point(0.5, 0.5)) for _ in range(8)]
    first = make_actor_at(municipality, "Antes", point(0.5, 0.5))
    expected = [str(first.id), *sorted(str(actor.id) for actor in made)]

    found = _features(client, box(0, 0))

    assert [feature["id"] for feature in found["features"]] == expected


def test_the_review_list_is_ordered_and_paged(client):
    municipality = signed_in_admin(client)
    made = [make_actor_at(municipality, "Igual", point(5, 5)) for _ in range(4)]
    for name in ("Zinc", "Ámbar"):
        make_actor_at(municipality, name, point(5, 5))

    def page(limit, offset):
        params = {"limit": limit, "offset": offset}
        items = client.get(f"{ACTORS}/unzoned", params=params).json()["items"]
        return [(item["title"], item["id"]) for item in items]

    everything = page(10, 0)
    assert [title for title, _ in everything] == ["Ámbar", *["Igual"] * 4, "Zinc"]
    assert [key for title, key in everything if title == "Igual"] == sorted(
        str(actor.id) for actor in made
    )
    assert page(2, 0) + page(2, 2) + page(2, 4) == everything


def test_the_grouping_squares_halve_with_every_zoom():
    assert features._cell(0) == (90, 72)
    assert features._cell(1) == (45, 36)
    width, height = features._cell(16)
    assert (width, height) == pytest.approx((0.001373291015625, 0.0010986328125))


def test_clusters_come_largest_first(client):
    municipality = signed_in_admin(client)
    for x, count in ((0, 2), (20, 5), (40, 3)):
        for _ in range(count):
            make_actor_at(municipality, "A", point(x, 0))

    found = _features(client, "-180,-90,180,90", 12)

    assert [cluster["count"] for cluster in found["clusters"]] == [5, 3, 2]


def test_squares_are_wider_than_tall(client):
    """In degrees; on screen, at these latitudes, they are about as wide as tall."""
    municipality = signed_in_admin(client)
    width, height = features._cell(14)
    # Inside one square, near its corners, and one just above and one just beside it.
    west, south = round(-62 / width) * width, round(-32 / height) * height
    for name, dx, dy in (
        ("Esquina", -0.45, -0.45),
        ("Otra esquina", 0.45, 0.45),
        ("Arriba", 0, 0.55),
        ("Al lado", 0.55, 0),
    ):
        location = {"type": "Point", "coordinates": [west + dx * width, south + dy * height]}
        make_actor_at(municipality, name, location)

    found = _features(client, "-63,-33,-61,-31", 14)

    assert [cluster["count"] for cluster in found["clusters"]] == [2]
    assert _titles(found) == ["Al lado", "Arriba"]


def test_the_map_is_truncated_at_low_zooms_too(client, monkeypatch):
    municipality = signed_in_admin(client)
    monkeypatch.setattr(features, "MAX_FEATURES", 2)
    for x in (0, 20):
        make_actor_at(municipality, f"A{x}", point(x, 0))
    world = "-180,-90,180,90"
    assert _features(client, world, 12)["truncated"] is False

    make_actor_at(municipality, "A40", point(40, 0))
    found = _features(client, world, 12)

    assert (found["truncated"], found["total"], _titles(found)) == (True, 3, ["A0", "A20"])
