"""The database keeps every record's zones up to date."""

import uuid

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from typer.testing import CliRunner

from gobernar360.cli import app as cli
from gobernar360.core.db import get_admin_engine, tenant_session
from gobernar360.dashboards.economic.models import Actor
from gobernar360.dashboards.projects.models import Project
from gobernar360.platform.geo.models import RecordZone, Zone, ZoneVersion
from tests.factories import admin_session, make_municipality
from tests.platform.geo.factories import (
    ZONES,
    line,
    make_actor_at,
    make_zone,
    point,
    signed_in_admin,
    square,
    zone_names,
)
from tests.projects.factories import make_axis, make_department, make_project, make_term

ACTORS = "/api/dashboards/economic/geo/actors"
PROJECTS = "/api/dashboards/projects/geo/projects"


def make_project_at(municipality, location, name="Pavimento") -> Project:
    term = make_term(municipality)
    project = make_project(
        municipality, term, make_axis(municipality, term), make_department(municipality), name=name
    )
    with admin_session() as session, session.begin():
        session.execute(update(Project).where(Project.id == project.id).values(location=location))
    return project


def _move(client, base, record, location):
    response = client.put(f"{base}/{record.id}/location", json={"location": location})
    assert response.status_code == 200, response.text
    return response.json()


def _assignments() -> int:
    with admin_session() as session:
        return len(session.execute(select(RecordZone)).all())


def test_a_point_is_assigned_to_the_zone_it_is_in(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Oeste", square(0, 0))
    make_zone(municipality, "Este", square(1, 0))

    east = make_actor_at(municipality, "Taller", point(1.5, 0.5))
    nowhere = make_actor_at(municipality, "Campo", point(5, 5))
    unlocated = make_actor_at(municipality, "Feria", None)

    assert [zone_names(actor) for actor in (east, nowhere, unlocated)] == [["Este"], [], []]
    listed = {
        a["name"]: a["zones"] for a in client.get("/api/dashboards/economic/actors").json()["items"]
    }
    assert [zone["name"] for zone in listed["Taller"]] == ["Este"]
    assert (listed["Campo"], listed["Feria"]) == ([], [])


def test_a_point_is_reassigned_when_it_moves(client):
    municipality = signed_in_admin(client)
    west = make_zone(municipality, "Oeste", square(0, 0))
    make_zone(municipality, "Este", square(1, 0))
    actor = make_actor_at(municipality, "Taller", point(1.5, 0.5))

    moved = _move(client, ACTORS, actor, point(0.5, 0.5))

    assert moved == {
        "location": point(0.5, 0.5),
        "kinds": ["Point"],
        "zones": [{"id": str(west.id), "name": "Oeste"}],
    }
    assert zone_names(actor) == ["Oeste"]
    assert _move(client, ACTORS, actor, point(9, 9))["zones"] == []
    assert _move(client, ACTORS, actor, None) == {
        "location": None,
        "kinds": ["Point"],
        "zones": [],
    }
    assert _assignments() == 0


def test_a_point_is_reassigned_when_the_boundary_moves(client):
    municipality = signed_in_admin(client)
    zone = make_zone(municipality, "Centro", square(0, 0))
    left = make_actor_at(municipality, "Sale", point(0.2, 0.2))
    stays = make_actor_at(municipality, "Queda", point(0.8, 0.8))
    joins = make_actor_at(municipality, "Entra", point(1.2, 1.2))

    client.patch(f"{ZONES}/{zone.id}", json={"boundary": square(0.5, 0.5), "base_version": 1})

    assert [zone_names(actor) for actor in (left, stays, joins)] == [[], ["Centro"], ["Centro"]]
    # What the boundary before had is still known.
    with admin_session() as session:
        before = set(
            session.scalars(
                select(RecordZone.record_id)
                .join(ZoneVersion, ZoneVersion.id == RecordZone.zone_version_id)
                .where(ZoneVersion.version == 1)
            )
        )
    assert before == {left.id, stays.id}


def test_a_zone_drawn_over_existing_records_takes_them(client):
    municipality = signed_in_admin(client)
    actor = make_actor_at(municipality, "Taller", point(0.5, 0.5))
    project = make_project_at(municipality, point(0.6, 0.6))

    client.post(ZONES, json={"name": "Centro", "boundary": square(0, 0)})

    assert zone_names(actor) == zone_names(project) == ["Centro"]


def test_a_line_counts_in_both_zones_it_crosses(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Oeste", square(0, 0))
    make_zone(municipality, "Este", square(1, 0))
    make_zone(municipality, "Norte", square(0, 5))

    street = make_project_at(municipality, line((0.5, 0.5), (1.5, 0.5)))

    assert zone_names(street) == ["Este", "Oeste"]
    detail = client.get(f"/api/dashboards/projects/projects/{street.id}").json()
    assert [zone["name"] for zone in detail["zones"]] == ["Este", "Oeste"]
    breakdown = client.get(f"{PROJECTS}/zones").json()
    assert {row["zone"]["name"]: row["values"]["active"] for row in breakdown["zones"]} == {
        "Este": 1,
        "Norte": 0,
        "Oeste": 1,
    }
    assert breakdown["total"]["values"]["active"] == 1


def test_a_street_along_the_border_belongs_to_both_sides(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Oeste", square(0, 0))
    make_zone(municipality, "Este", square(1, 0))

    street = make_project_at(municipality, line((1, 0.2), (1, 0.8)))

    assert zone_names(street) == ["Este", "Oeste"]


def test_a_line_that_only_ends_at_a_border_does_not_cross_the_zone(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Oeste", square(0, 0))
    make_zone(municipality, "Este", square(1, 0))

    # Also its box overlaps a zone the line itself does not enter.
    make_zone(municipality, "Rincón", square(0.6, 0, 0.2))
    street = make_project_at(municipality, line((0.2, 0.2), (0.5, 0.9), (1, 0.9)))

    assert zone_names(street) == ["Oeste"]


def test_a_record_where_zones_overlap_is_in_both_and_counted_once_in_the_total(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Barrio", square(0, 0))
    make_zone(municipality, "Distrito", square(0, 0, 3))
    actor = make_actor_at(municipality, "Taller", point(0.5, 0.5))

    assert zone_names(actor) == ["Barrio", "Distrito"]
    breakdown = client.get(f"{ACTORS}/zones").json()
    assert [row["values"]["actors"] for row in breakdown["zones"]] == [1, 1]
    assert breakdown["total"]["values"]["actors"] == 1


def test_a_hole_in_a_zone_is_not_the_zone(client):
    municipality = signed_in_admin(client)
    outer, hole = square(0, 0)["coordinates"][0], square(0.4, 0.4, 0.2)["coordinates"][0]
    make_zone(municipality, "Centro", {"type": "Polygon", "coordinates": [outer, hole]})

    inside = make_actor_at(municipality, "Plaza", point(0.5, 0.5))

    assert zone_names(inside) == []


def test_a_retired_zone_no_longer_has_records(client):
    municipality = signed_in_admin(client)
    zone = make_zone(municipality)
    actor = make_actor_at(municipality, "Taller", point(0.5, 0.5))

    client.delete(f"{ZONES}/{zone.id}")

    assert zone_names(actor) == []
    assert client.get(f"{ACTORS}/{actor.id}/location").json()["zones"] == []
    assert client.get(f"{ACTORS}/unzoned").json()["total"] == 1


def test_deleting_a_record_leaves_nothing_behind(client):
    municipality = signed_in_admin(client)
    make_zone(municipality)
    actor = make_actor_at(municipality, "Taller", point(0.5, 0.5))

    assert client.delete(f"/api/dashboards/economic/actors/{actor.id}").status_code == 204

    assert _assignments() == 0


def test_deleting_a_zone_row_leaves_nothing_behind():
    municipality = make_municipality()
    make_zone(municipality)
    make_actor_at(municipality, "Taller", point(0.5, 0.5))

    with admin_session() as session, session.begin():
        session.execute(delete(Zone))

    assert _assignments() == 0


def test_the_database_only_takes_the_kinds_of_location_a_record_accepts():
    municipality = make_municipality()
    actor = make_actor_at(municipality, "Taller", None)
    project = make_project_at(municipality, None)

    with pytest.raises(DBAPIError, match="LineString"), admin_session() as session:
        session.execute(
            update(Actor).where(Actor.id == actor.id).values(location=line((0, 0), (1, 1)))
        )
    with pytest.raises(IntegrityError, match="location_kind"), admin_session() as session:
        session.execute(
            update(Project).where(Project.id == project.id).values(location=square(0, 0))
        )


# In bulk


def _without_triggers(statement: str, **values) -> None:
    with get_admin_engine().begin() as connection:
        connection.execute(text("SET LOCAL session_replication_role = replica"))
        connection.execute(text(statement), values)


def test_the_command_works_out_every_assignment_again():
    noetinger, saira = make_municipality(), make_municipality("Saira")
    zone = make_zone(noetinger, "Centro", square(0, 0))
    make_zone(saira, "Centro", square(0, 0))
    missing = make_actor_at(noetinger, "Falta", point(0.5, 0.5))
    gone = make_actor_at(noetinger, "Sobra", point(0.6, 0.6))
    theirs = make_actor_at(saira, "Ajeno", point(0.5, 0.5))
    _without_triggers("DELETE FROM record_zones WHERE record_id = :id", id=missing.id)
    _without_triggers("UPDATE economic_actors SET location = NULL WHERE id = :id", id=gone.id)
    # Left by a record, and a kind of record, that no longer exist.
    for table in ("economic_actors", "old_table"):
        with admin_session() as session, session.begin():
            version = session.scalar(select(ZoneVersion.id).where(ZoneVersion.zone_id == zone.id))
            session.add(
                RecordZone(
                    municipality_id=noetinger.id,
                    zone_version_id=version,
                    record_table=table,
                    record_id=uuid.uuid4(),
                )
            )

    first = CliRunner().invoke(cli, ["assign-zones"])
    second = CliRunner().invoke(cli, ["assign-zones"])

    assert first.exit_code == 0, first.output
    assert first.output.splitlines() == [
        "Noetinger: 1 assignments added, 3 removed.",
        "Saira: 0 assignments added, 0 removed.",
    ]
    assert second.output.splitlines()[0] == "Noetinger: 0 assignments added, 0 removed."
    assert [zone_names(actor) for actor in (missing, gone, theirs)] == [["Centro"], [], ["Centro"]]
    assert _assignments() == 2


# Isolation


def test_records_are_never_assigned_to_another_municipalitys_zones(client):
    noetinger, saira = signed_in_admin(client), make_municipality("Saira")
    mine = make_zone(noetinger, "Centro", square(0, 0))
    make_zone(saira, "Ajena", square(0, 0))
    actor = make_actor_at(noetinger, "Taller", point(0.5, 0.5))
    theirs = make_actor_at(saira, "Ajeno", point(0.5, 0.5))

    # Built as the owner, who bypasses row-level security: the triggers isolate by themselves.
    assert (zone_names(actor), zone_names(theirs)) == (["Centro"], ["Ajena"])
    # And so does every change made through the API.
    client.patch(f"{ZONES}/{mine.id}", json={"boundary": square(0, 0, 2), "base_version": 1})
    _move(client, ACTORS, actor, point(0.6, 0.6))
    assert (zone_names(actor), zone_names(theirs)) == (["Centro"], ["Ajena"])


def test_every_geometry_table_is_isolated_between_municipalities():
    noetinger, saira = make_municipality(), make_municipality("Saira")
    for municipality in (noetinger, saira):
        make_zone(municipality, "Centro", square(0, 0))
        make_actor_at(municipality, "Taller", point(0.5, 0.5))

    with tenant_session(noetinger.id) as db:
        for model in (Zone, ZoneVersion, RecordZone, Actor):
            owners = {row.municipality_id for row in db.scalars(select(model))}
            assert owners == {noetinger.id}, model
        # A purely spatial question, with no other condition.
        found = db.scalar(
            text(
                "SELECT count(*) FROM economic_actors, zone_versions "
                "WHERE ST_Intersects(location, boundary)"
            )
        )
    assert found == 1


def test_a_municipality_cannot_write_assignments_for_another():
    noetinger, saira = make_municipality(), make_municipality("Saira")
    make_zone(saira)
    with admin_session() as session:
        version = session.scalar(select(ZoneVersion.id))

    with pytest.raises(DBAPIError, match="row-level security"):
        with tenant_session(noetinger.id) as db:
            db.add(
                RecordZone(
                    municipality_id=saira.id,
                    zone_version_id=version,
                    record_table="economic_actors",
                    record_id=uuid.uuid4(),
                )
            )
