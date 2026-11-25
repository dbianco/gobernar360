"""Zones: what is accepted, reported and kept of their past."""

from datetime import datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from gobernar360.platform.geo.models import Zone, ZoneVersion
from gobernar360.platform.models import AuditLog
from tests.factories import admin_session, login, make_membership, make_municipality, make_user
from tests.platform.geo.factories import (
    ZONES,
    admin_of,
    at,
    make_zone,
    ring,
    signed_in_admin,
    square,
)

BOWTIE = {"type": "Polygon", "coordinates": [[at(0, 0), at(1, 1), at(1, 0), at(0, 1), at(0, 0)]]}


def _create(client, name="Centro", boundary=None):
    return client.post(ZONES, json={"name": name, "boundary": boundary or square(0, 0)})


def _created(client, name="Centro", boundary=None) -> dict:
    response = _create(client, name, boundary)
    assert response.status_code == 201, response.text
    return response.json()["zone"]


def _error(response) -> tuple[int, str, str]:
    error = response.json()["error"]
    return response.status_code, error["code"], error["message"]


def test_administrator_draws_a_zone_and_every_member_sees_it(client):
    municipality = signed_in_admin(client)
    make_membership(make_user("leo@noetinger.test"), municipality)

    response = _create(client, "  Barrio Norte ")

    assert response.status_code == 201
    zone = response.json()["zone"]
    assert response.json()["overlaps"] == []
    assert (zone["name"], zone["version"]) == ("Barrio Norte", 1)
    assert zone["boundary"] == {"type": "MultiPolygon", "coordinates": [[ring(0, 0)]]}
    assert datetime.fromisoformat(zone["valid_from"]).tzinfo is not None
    client.post("/api/auth/logout")
    login(client, "leo@noetinger.test")
    assert client.get("/api/zones").json() == [zone]


def test_zones_come_by_name_ignoring_accents(client):
    signed_in_admin(client)
    for index, name in enumerate(("Oeste", "Ámbar", "Centro")):
        _created(client, name, square(index * 2, 0))

    assert [zone["name"] for zone in client.get("/api/zones").json()] == [
        "Ámbar",
        "Centro",
        "Oeste",
    ]


def test_zones_need_a_session_and_managing_them_needs_an_administrator(client):
    assert client.get("/api/zones").status_code == 401
    municipality = make_municipality()
    zone = make_zone(municipality)
    make_membership(make_user("carla@noetinger.test"), municipality, grants={"projects": "admin"})
    login(client, "carla@noetinger.test")

    refused = [
        _create(client),
        client.get(f"{ZONES}/overlaps"),
        client.post(f"{ZONES}/import", json={"geojson": {}}),
        client.patch(f"{ZONES}/{zone.id}", json={"name": "x"}),
        client.delete(f"{ZONES}/{zone.id}"),
        client.get(f"{ZONES}/{zone.id}/versions"),
    ]

    assert [response.status_code for response in refused] == [403] * 6
    assert [z["name"] for z in client.get("/api/zones").json()] == ["Centro"]


def test_a_boundary_that_crosses_itself_is_rejected(client):
    signed_in_admin(client)

    status, code, message = _error(_create(client, boundary=BOWTIE))

    assert (status, code) == (422, "zone_self_intersects")
    assert message.startswith("The boundary crosses itself: Self-intersection[-61.995")
    assert client.get("/api/zones").json() == []


def test_a_boundary_that_is_not_closed_is_rejected(client):
    signed_in_admin(client)
    open_ring = {"type": "Polygon", "coordinates": [ring(0, 0)[:-1]]}

    assert _error(_create(client, boundary=open_ring)) == (
        422,
        "zone_not_closed",
        "The boundary is not closed: its last corner must be its first one.",
    )


def test_a_zone_without_ground_is_rejected(client):
    signed_in_admin(client)
    # About 1 m by 1 m.
    speck = square(0, 0, 0.001)

    assert _error(_create(client, boundary=speck)) == (
        422,
        "invalid_boundary",
        "The zone encloses almost no area.",
    )


def test_the_database_refuses_an_invalid_boundary_by_itself(client):
    municipality = make_municipality()
    zone = make_zone(municipality)

    with pytest.raises(IntegrityError, match="boundary_valid"), admin_session() as session:
        session.execute(
            text(
                "UPDATE zone_versions SET boundary = "
                "ST_GeomFromText('MULTIPOLYGON(((0 0,1 1,1 0,0 1,0 0)))', 4326) "
                "WHERE zone_id = :id"
            ),
            {"id": zone.id},
        )


def test_two_zones_in_use_cannot_share_a_name(client):
    signed_in_admin(client)
    zone = _created(client, "Centro")
    other = _created(client, "Norte", square(5, 5))

    taken = (409, "zone_name_exists", "Another zone already has this name.")
    assert _error(_create(client, "CENTRO", square(9, 9))) == taken
    assert _error(client.patch(f"{ZONES}/{other['id']}", json={"name": "centro"})) == taken
    # Its own name, written otherwise, is not somebody else's.
    renamed = client.patch(f"{ZONES}/{zone['id']}", json={"name": "CENTRO"})
    assert renamed.json()["zone"]["name"] == "CENTRO"


def test_the_database_has_the_last_word_on_repeated_names():
    municipality = make_municipality()
    make_zone(municipality, "Centro")

    with pytest.raises(IntegrityError, match="uq_zones_municipality_id_name"):
        make_zone(municipality, "CENTRO")
    make_zone(make_municipality("Saira"), "Centro")


def test_overlapping_zones_are_saved_and_reported(client):
    signed_in_admin(client)
    centro = _created(client, "Centro", square(0, 0))
    _created(client, "Lejos", square(10, 10))

    response = _create(client, "Norte", square(0, 0.5))

    assert response.status_code == 201
    [overlap] = response.json()["overlaps"]
    assert overlap["zone"] == {"id": centro["id"], "name": "Centro"}
    assert overlap["other"]["name"] == "Norte"
    # Half of a square of about 945 m by 1109 m.
    assert overlap["area_m2"] == pytest.approx(523_600, rel=0.01)
    assert client.get(f"{ZONES}/overlaps").json() == [overlap]


def test_neighbours_that_share_a_border_do_not_overlap(client):
    signed_in_admin(client)
    _created(client, "Centro", square(0, 0))

    # Beside it, at a corner, and drawn a few centimetres into it.
    for name, boundary in (
        ("Este", square(1, 0)),
        ("Noreste", square(1, 1)),
        ("Norte", square(0, 0.9999995)),
    ):
        assert _create(client, name, boundary).json()["overlaps"] == []

    assert client.get(f"{ZONES}/overlaps").json() == []


def test_overlaps_are_listed_largest_first(client):
    signed_in_admin(client)
    _created(client, "A", square(0, 0))
    _created(client, "B", square(0.9, 0))
    _created(client, "C", square(0, 0.2))

    found = client.get(f"{ZONES}/overlaps").json()

    assert [(o["zone"]["name"], o["other"]["name"]) for o in found] == [
        ("A", "C"),
        ("A", "B"),
        ("B", "C"),
    ]


def test_moving_a_boundary_adds_a_version_and_keeps_the_one_before(client):
    signed_in_admin(client)
    zone = _created(client, "Centro", square(0, 0))

    moved = client.patch(
        f"{ZONES}/{zone['id']}", json={"boundary": square(5, 5), "base_version": 1}
    ).json()["zone"]
    newest, oldest = client.get(f"{ZONES}/{zone['id']}/versions").json()

    assert (moved["id"], moved["version"]) == (zone["id"], 2)
    assert moved["boundary"]["coordinates"] == [[ring(5, 5)]]
    assert (newest["version"], newest["valid_to"]) == (2, None)
    assert (oldest["version"], oldest["boundary"]) == (1, zone["boundary"])
    # One ends the moment the other starts.
    assert oldest["valid_to"] == newest["valid_from"]


def test_renaming_or_saving_the_same_boundary_adds_no_version(client):
    signed_in_admin(client)
    zone = _created(client, "Centro", square(0, 0))
    # The same square, from another corner.
    corners = ring(0, 0)[:-1]
    same = {"type": "Polygon", "coordinates": [[*corners[2:], *corners[:2], corners[2]]]}

    client.patch(f"{ZONES}/{zone['id']}", json={"name": "Microcentro", "boundary": same})

    [version] = client.get(f"{ZONES}/{zone['id']}/versions").json()
    assert version["version"] == 1
    assert [z["name"] for z in client.get("/api/zones").json()] == ["Microcentro"]


def test_nobody_moves_a_boundary_they_have_not_seen(client):
    signed_in_admin(client)
    zone = _created(client)
    path = f"{ZONES}/{zone['id']}"
    client.patch(path, json={"boundary": square(3, 3), "base_version": 1})

    late = client.patch(path, json={"boundary": square(7, 7), "base_version": 1})

    assert _error(late) == (
        409,
        "zone_changed",
        "Somebody else changed the boundary of this zone in the meantime.",
    )
    [current] = client.get("/api/zones").json()
    assert current["boundary"]["coordinates"] == [[ring(3, 3)]]


def test_an_invalid_new_boundary_leaves_the_zone_as_it_was(client):
    signed_in_admin(client)
    zone = _created(client)

    response = client.patch(f"{ZONES}/{zone['id']}", json={"name": "Otro", "boundary": BOWTIE})

    assert _error(response)[:2] == (422, "zone_self_intersects")
    assert client.get("/api/zones").json() == [zone]


def test_a_retired_zone_leaves_its_name_free_and_its_versions_readable(client):
    signed_in_admin(client)
    zone = _created(client)
    path = f"{ZONES}/{zone['id']}"

    assert client.delete(path).status_code == 204

    assert client.get("/api/zones").json() == []
    [version] = client.get(f"{path}/versions").json()
    assert version["valid_to"] is not None
    assert client.delete(path).status_code == 404
    assert client.patch(path, json={"name": "x"}).status_code == 404
    assert _created(client, "Centro")["version"] == 1
    missing = f"{ZONES}/00000000-0000-0000-0000-000000000000/versions"
    assert client.get(missing).status_code == 404


def test_zone_requests_are_checked(client):
    signed_in_admin(client)
    zone = _created(client)
    path = f"{ZONES}/{zone['id']}"

    assert _error(_create(client, "  "))[:2] == (422, "validation_error")
    assert _error(client.post(ZONES, json={"name": "x"}))[:2] == (422, "validation_error")
    assert _error(client.patch(path, json={"name": None}))[:2] == (422, "validation_error")
    assert _error(client.patch(path, json={"boundary": None}))[:2] == (422, "validation_error")
    assert _error(client.patch(path, json={"other": 1}))[:2] == (422, "validation_error")


def test_changes_to_zones_are_audited(client):
    signed_in_admin(client)
    zone = _created(client)
    client.patch(f"{ZONES}/{zone['id']}", json={"boundary": square(3, 3)})

    with admin_session() as session:
        entries = session.execute(
            select(AuditLog.action, AuditLog.entity_type).order_by(AuditLog.created_at)
        ).all()
        authors = set(session.scalars(select(ZoneVersion.created_by)))

    assert sorted(map(tuple, entries)) == [
        ("create", "zone_versions"),
        ("create", "zone_versions"),
        ("create", "zones"),
        ("update", "zone_versions"),
    ]
    assert len(authors) == 1 and None not in authors


# GeoJSON files


def _feature(name, geometry, key="name") -> dict:
    return {"type": "Feature", "properties": {key: name}, "geometry": geometry}


def _import(client, *features):
    geojson = {"type": "FeatureCollection", "features": list(features)}
    return client.post(f"{ZONES}/import", json={"geojson": geojson})


def test_a_file_creates_moves_and_leaves_zones(client):
    signed_in_admin(client)
    _created(client, "Centro", square(0, 0))
    _created(client, "Norte", square(2, 2))

    response = _import(
        client,
        _feature("CENTRO", square(0, 0)),
        _feature("Norte", square(2, 2.5), key="Nombre"),
        _feature(" Sur ", square(2, 3)),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["created"], body["moved"], body["unchanged"]) == (1, 1, 1)
    assert [(o["zone"]["name"], o["other"]["name"]) for o in body["overlaps"]] == [("Norte", "Sur")]
    assert [(z["name"], z["version"]) for z in client.get("/api/zones").json()] == [
        ("Centro", 1),
        ("Norte", 2),
        ("Sur", 1),
    ]


def test_a_file_with_any_problem_changes_nothing_and_names_them_all(client):
    signed_in_admin(client)

    response = _import(
        client,
        _feature("Bien", square(0, 0)),
        _feature("Cruzada", BOWTIE),
        _feature("", square(2, 0)),
        _feature("bien", square(4, 0)),
        _feature("Punto", {"type": "Point", "coordinates": [0, 0]}),
        _feature("Abierta", {"type": "Polygon", "coordinates": [ring(0, 0)[:-1]]}),
        {"type": "Feature", "geometry": square(6, 0)},
        "nada",
        _feature(7, square(8, 0)),
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "zone_file_invalid",
        "message": "The file was not imported: some zones have problems.",
        "details": [
            {"row": 2, "name": "Cruzada", "code": "zone_self_intersects"},
            {"row": 3, "name": None, "code": "no_name"},
            {"row": 4, "name": "bien", "code": "repeated_name"},
            {"row": 5, "name": "Punto", "code": "invalid_boundary"},
            {"row": 6, "name": "Abierta", "code": "zone_not_closed"},
            {"row": 7, "name": None, "code": "no_name"},
            {"row": 8, "name": None, "code": "no_name"},
            {"row": 9, "name": None, "code": "no_name"},
        ],
    }
    assert client.get("/api/zones").json() == []


@pytest.mark.parametrize(
    ("geojson", "code"),
    [
        ({}, "not_a_collection"),
        ({"type": "FeatureCollection"}, "not_a_collection"),
        ({"type": "Polygon", "features": []}, "not_a_collection"),
        ({"type": "FeatureCollection", "features": []}, "empty"),
        ({"type": "FeatureCollection", "features": [{}] * 301}, "too_many"),
    ],
)
def test_a_file_that_is_not_a_collection_of_zones_is_refused(client, geojson, code):
    signed_in_admin(client)

    error = client.post(f"{ZONES}/import", json={"geojson": geojson}).json()["error"]

    assert (error["code"], error["details"]) == (
        "zone_file_invalid",
        [{"row": 0, "name": None, "code": code}],
    )


# Isolation


def test_two_municipalities_with_overlapping_zones_never_see_each_other(client):
    noetinger, saira = make_municipality(), make_municipality("Saira")
    admin_of(noetinger)
    admin_of(saira, "admin@saira.test")
    theirs = make_zone(saira, "Centro", square(0, 0))
    login(client, "admin@noetinger.test")

    # Over the other municipality's zone, with its name: neither reported nor in the way.
    created = _create(client, "Centro", square(0.5, 0.5))

    assert created.status_code == 201 and created.json()["overlaps"] == []
    assert client.get(f"{ZONES}/overlaps").json() == []
    assert [z["id"] for z in client.get("/api/zones").json()] == [created.json()["zone"]["id"]]
    path = f"{ZONES}/{theirs.id}"
    assert client.patch(path, json={"boundary": square(9, 9)}).status_code == 404
    assert client.delete(path).status_code == 404
    assert client.get(f"{path}/versions").status_code == 404
    imported = _import(client, _feature("Centro", square(0.5, 0.5)))
    assert imported.json()["unchanged"] == 1
    with admin_session() as session:
        untouched = session.get(Zone, theirs.id)
        assert (untouched.name, untouched.retired_at) == ("Centro", None)
        assert session.scalars(
            select(ZoneVersion.version).where(ZoneVersion.zone_id == theirs.id)
        ).all() == [1]


def test_the_audit_trail_says_what_was_done_to_a_zone(client):
    municipality = signed_in_admin(client)
    zone = _created(client, "Centro")
    path = f"{ZONES}/{zone['id']}"
    client.patch(path, json={"name": "Casco"})
    client.patch(path, json={"boundary": square(3, 3)})
    client.delete(path)

    with admin_session() as session:
        entries = session.scalars(
            select(AuditLog)
            .where(AuditLog.municipality_id == municipality.id)
            .order_by(AuditLog.created_at)
        ).all()
    done = [(e.entity_type, e.action, e.changes) for e in entries]
    # Several entries share the moment of their request.
    for entry in (
        ("zones", "create", {"name": "Centro"}),
        ("zone_versions", "create", {"zone_id": zone["id"], "version": 1}),
        ("zones", "update", {"name": "Casco"}),
        ("zone_versions", "create", {"zone_id": zone["id"], "version": 2}),
    ):
        assert entry in done
    closed = [(kind, sorted(changes)) for kind, action, changes in done if action == "update"]
    assert closed.count(("zone_versions", ["valid_to"])) == 2
    assert closed.count(("zones", ["retired_at"])) == 1


def test_saving_a_zone_reports_only_its_own_overlaps(client):
    signed_in_admin(client)
    _created(client, "A", square(0, 0))
    _created(client, "B", square(0.5, 0))

    apart = _create(client, "C", square(10, 10)).json()
    moved = client.patch(
        f"{ZONES}/{apart['zone']['id']}", json={"boundary": square(0.9, 0.5)}
    ).json()

    assert apart["overlaps"] == []
    assert [(o["zone"]["name"], o["other"]["name"]) for o in moved["overlaps"]] == [
        ("B", "C"),
        ("A", "C"),
    ]


def test_a_file_has_as_many_zones_as_a_municipality_may_need_and_names_that_fit(client):
    signed_in_admin(client)
    features = [_feature(f"Zona {n}", square(n % 20, n // 20, 0.5)) for n in range(299)]

    long = _import(client, *features, _feature("x" * 250, square(30, 30)))

    assert long.status_code == 200, long.text
    assert long.json()["created"] == 300
    assert max(len(zone["name"]) for zone in client.get("/api/zones").json()) == 200


def test_the_least_ground_a_zone_may_enclose(client):
    signed_in_admin(client)
    # At this latitude a thousandth of a unit is about 0.95 m by 1.11 m.
    assert _create(client, "Chica", square(0, 0, 0.003)).status_code == 422
    assert _create(client, "Apenas", square(0, 0, 0.0034)).status_code == 201


def test_coordinates_are_kept_to_the_centimetre(client):
    signed_in_admin(client)
    exact = {"type": "Polygon", "coordinates": [[
        [-62.12345678, -32.12345678], [-62.1, -32.12345678], [-62.1, -32.1],
        [-62.12345678, -32.12345678],
    ]]}  # fmt: skip

    zone = _created(client, "Exacta", exact)

    assert zone["boundary"]["coordinates"][0][0][0] == [-62.1234568, -32.1234568]
