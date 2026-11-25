"""A dashboard the platform has never heard of gets maps and zones by declaring its records."""

import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import String, Uuid, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from gobernar360.core.db import enable_tenant_rls, get_admin_engine
from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import DashboardModule
from gobernar360.platform.access import AccessLevel
from gobernar360.platform.geo.contract import LocatedRecord, ZoneMetric
from gobernar360.platform.geo.located import (
    LINE,
    POINT,
    LocatedMixin,
    disable_location,
    enable_location,
)
from gobernar360.platform.geo.models import RecordZone
from tests.factories import admin_session, login, make_membership, make_municipality, make_user
from tests.platform.geo.factories import ZONES, admin_of, line, make_zone, point, square

TREES = "/api/dashboards/parks/geo/trees"


class ParksBase(DeclarativeBase):
    """Apart from the application's models, whose schema the migrations must match."""


class Tree(LocatedMixin, ParksBase):
    __tablename__ = "parks_trees"
    location_kinds = (POINT, LINE)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    municipality_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    species: Mapped[str] = mapped_column(String(100))
    height: Mapped[int]


class TreeFilters(BaseModel):
    species: str | None = None


trees = LocatedRecord(
    key="trees",
    model=Tree,
    title=Tree.species,
    filters=TreeFilters,
    conditions=lambda ctx, today, filters: (
        [Tree.species == filters.species] if filters.species else []
    ),
    metrics=(
        ZoneMetric("trees", lambda today, filters: func.count(Tree.id)),
        ZoneMetric("height", lambda today, filters: func.sum(Tree.height), unit="money"),
    ),
)


@pytest.fixture(scope="module")
def parks_table(migrated_database):
    """What the dashboard's migration would do."""
    with get_admin_engine().begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE parks_trees (id uuid PRIMARY KEY, municipality_id uuid NOT NULL, "
                "species varchar(100) NOT NULL, height integer NOT NULL)"
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            enable_tenant_rls("parks_trees")
            enable_location("parks_trees", Tree.location_kinds)
    yield
    with get_admin_engine().begin() as connection:
        connection.execute(text("DROP TABLE parks_trees"))


@pytest.fixture
def parks(parks_table):
    def install(*located: LocatedRecord):
        registry.register(
            DashboardModule(
                key="parks",
                router=APIRouter(),
                get_summary=lambda ctx, today: [],
                located=located or (trees,),
            )
        )

    install()
    yield install
    registry.unregister("parks")
    with get_admin_engine().begin() as connection:
        connection.execute(text("DELETE FROM parks_trees"))


def _plant(municipality, species, location, height=3) -> Tree:
    tree = Tree(municipality_id=municipality.id, species=species, location=location, height=height)
    with admin_session() as session, session.begin():
        session.add(tree)
    return tree


def test_a_dashboard_registered_only_in_a_test_declares_located_records(client, parks):
    municipality = admin_of(None, "admin@noetinger.test", "parks")
    login(client, "admin@noetinger.test")
    ceibo = _plant(municipality, "Ceibo", point(0.5, 0.5))
    _plant(municipality, "Alameda", line((0.2, 0.2), (3, 0.2)), height=7)

    # Drawn afterwards: the platform finds the dashboard's records by itself.
    zone = client.post(ZONES, json={"name": "Centro", "boundary": square(0, 0)}).json()["zone"]

    area = ",".join(str(n) for n in (*point(0, 0)["coordinates"], *point(1, 1)["coordinates"]))
    shown = client.get(f"{TREES}/features", params={"bbox": area, "zoom": 18}).json()
    assert [feature["title"] for feature in shown["features"]] == ["Alameda", "Ceibo"]
    only = client.get(
        f"{TREES}/features", params={"bbox": area, "zoom": 18, "species": "Ceibo"}
    ).json()
    assert [feature["title"] for feature in only["features"]] == ["Ceibo"]

    breakdown = client.get(f"{TREES}/zones").json()
    assert breakdown["zones"][0]["values"] == {"trees": 2, "height": "10.00"}
    moved = client.put(f"{TREES}/{ceibo.id}/location", json={"location": point(8, 8)}).json()
    assert moved["zones"] == []
    review = client.get(f"{TREES}/unzoned").json()
    assert [item["title"] for item in review["items"]] == ["Ceibo"]
    [section] = client.get(f"/api/overview/zones/{zone['id']}").json()["sections"]
    assert (section["dashboard_key"], section["record_key"]) == ("parks", "trees")
    assert section["values"] == {"trees": 1, "height": "7.00"}


def test_it_may_keep_its_records_from_viewers(client, parks):
    parks(
        LocatedRecord(
            key="trees",
            model=Tree,
            title=Tree.species,
            metrics=trees.metrics,
            individual_level=AccessLevel.ADMIN,
        )
    )
    municipality = make_municipality()
    make_zone(municipality, "Centro", square(0, 0))
    for index in range(6):
        _plant(municipality, f"Ceibo {index}", point(0.5, 0.5))
    tree = _plant(municipality, "Ombú", point(7, 7))
    make_membership(make_user("carla@noetinger.test"), municipality, grants={"parks": "editor"})
    login(client, "carla@noetinger.test")

    assert client.get(f"{TREES}/{tree.id}/location").status_code == 403
    # Whoever cannot see a location cannot set it either.
    answer = client.put(f"{TREES}/{tree.id}/location", json={"location": point(1, 1)})
    assert answer.status_code == 403
    body = client.get(f"{TREES}/zones").json()
    # One tree is outside: hiding only that would leave it at the total minus the zone.
    assert body["zones"][0]["values"] == {"trees": None, "height": None}
    # Filters are the ones the record declares: none.
    assert client.get(f"{TREES}/zones", params={"species": "Ombú"}).json() == body


def test_its_records_are_isolated_like_any_other(client, parks):
    saira = make_municipality("Saira")
    admin_of(None, "admin@noetinger.test", "parks")
    make_zone(saira, "Ajena", square(0, 0))
    theirs = _plant(saira, "Ajeno", point(0.5, 0.5))
    login(client, "admin@noetinger.test")

    client.post(ZONES, json={"name": "Centro", "boundary": square(0, 0)})

    assert client.get(f"{TREES}/zones").json()["total"]["values"]["trees"] == 0
    assert client.get(f"{TREES}/{theirs.id}/location").status_code == 404


def test_a_dashboard_without_located_records_has_no_map(client, demo_dashboard):
    admin_of(None, "admin@noetinger.test", "demo")
    login(client, "admin@noetinger.test")

    assert client.get("/api/dashboards/demo/geo/trees/zones").status_code == 404


def test_a_dashboard_can_take_the_location_of_its_records_away(client, parks):
    municipality = admin_of(None, "admin@noetinger.test", "parks")
    make_zone(municipality, "Centro", square(0, 0))
    _plant(municipality, "Ceibo", point(0.5, 0.5))
    with admin_session() as session:
        assert session.scalar(select(func.count()).select_from(RecordZone)) == 1

    # What the downgrade of its migration does, undone so that other tests find the table.
    with get_admin_engine().connect() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            disable_location("parks_trees")
        columns = connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'parks_trees'"
            )
        ).scalars()
        assert "location" not in set(columns)
        assert connection.scalar(select(func.count()).select_from(RecordZone)) == 0
        connection.rollback()
