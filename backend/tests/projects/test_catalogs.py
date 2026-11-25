"""The plan's catalogs: each is listed, added to, renamed and deleted the same way."""

import uuid

import pytest
from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform.models import AuditLog
from tests.factories import login, make_membership, make_municipality, make_user
from tests.projects.factories import (
    make_axis,
    make_department,
    make_objective,
    make_owner,
    make_program,
    make_term,
    projects_member,
)

BASE = "/api/dashboards/projects"
CATALOGS = ("axes", "objectives", "departments", "programs", "owners")
TABLES = {name: f"projects_{name}" for name in CATALOGS}


def _name_field(catalog: str) -> str:
    return "full_name" if catalog == "owners" else "name"


@pytest.fixture
def plan(client):
    municipality = projects_member("admin")
    term = make_term(municipality)
    login(client, "ana@noetinger.test")
    return {"municipality": municipality, "term": term, "axis": make_axis(municipality, term, "Z")}


def _parent(plan, catalog: str) -> dict:
    """What a new entry belongs to."""
    return {
        "axes": {"term_id": str(plan["term"].id)},
        "objectives": {"axis_id": str(plan["axis"].id)},
    }.get(catalog, {})


def _names(client, catalog: str) -> list[str]:
    return [item[_name_field(catalog)] for item in client.get(f"{BASE}/{catalog}").json()]


@pytest.mark.parametrize("catalog", CATALOGS)
def test_an_entry_is_added_renamed_and_deleted(client, plan, catalog):
    field, parent = _name_field(catalog), _parent(plan, catalog)

    created = client.post(f"{BASE}/{catalog}", json=parent | {field: "  Primero "})
    path = f"{BASE}/{catalog}/{created.json()['id']}"
    renamed = client.patch(path, json={field: "Segundo"})

    assert created.status_code == 201
    assert created.json() == parent | {"id": created.json()["id"], field: "Primero"}
    assert renamed.json() == created.json() | {field: "Segundo"}
    assert "Segundo" in _names(client, catalog)
    assert client.delete(path).status_code == 204
    assert "Segundo" not in _names(client, catalog)
    with tenant_session(plan["municipality"].id) as db:
        entries = db.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == TABLES[catalog])
            .order_by(AuditLog.created_at)
        ).all()
    assert [(e.action, (e.changes or {}).get(field)) for e in entries] == [
        ("create", "Primero"),
        ("update", "Segundo"),
        ("delete", None),
    ]
    assert {e.entity_id for e in entries} == {created.json()["id"]}


@pytest.mark.parametrize("catalog", CATALOGS)
def test_entries_come_by_name(client, plan, catalog):
    for name in ("Centro", "Agua", "Barrios"):
        client.post(f"{BASE}/{catalog}", json=_parent(plan, catalog) | {_name_field(catalog): name})

    assert [name for name in _names(client, catalog) if name != "Z"] == [
        "Agua",
        "Barrios",
        "Centro",
    ]


@pytest.mark.parametrize("catalog", CATALOGS)
def test_an_entry_needs_a_name_and_must_exist_to_be_changed(client, plan, catalog):
    field, missing = _name_field(catalog), f"{BASE}/{catalog}/{uuid.uuid4()}"

    blank = client.post(f"{BASE}/{catalog}", json=_parent(plan, catalog) | {field: "  "})

    assert blank.status_code == 422
    for response in (client.patch(missing, json={field: "x"}), client.delete(missing)):
        assert response.status_code == 404
        assert response.json()["error"] == {"code": "not_found", "message": "Resource not found."}


@pytest.mark.parametrize("catalog", CATALOGS)
def test_only_the_dashboards_administrators_change_a_catalog(client, plan, catalog):
    field = _name_field(catalog)
    entry = client.post(f"{BASE}/{catalog}", json=_parent(plan, catalog) | {field: "Uno"}).json()
    make_membership(
        make_user("carla@noetinger.test"), plan["municipality"], grants={"projects": "editor"}
    )
    client.post("/api/auth/logout")
    login(client, "carla@noetinger.test")
    path = f"{BASE}/{catalog}/{entry['id']}"

    assert "Uno" in _names(client, catalog)
    refused = (
        client.post(f"{BASE}/{catalog}", json=_parent(plan, catalog) | {field: "Dos"}),
        client.patch(path, json={field: "Dos"}),
        client.delete(path),
    )
    assert [response.status_code for response in refused] == [403, 403, 403]
    assert "Uno" in _names(client, catalog)


@pytest.mark.parametrize("catalog", CATALOGS)
def test_another_municipalitys_entries_are_not_there(client, plan, catalog):
    other = make_municipality("Saira")
    term = make_term(other)
    axis = make_axis(other, term, "Ajeno")
    theirs = {
        "axes": axis,
        "objectives": make_objective(other, axis, "Ajeno"),
        "departments": make_department(other, "Ajeno"),
        "programs": make_program(other, "Ajeno"),
        "owners": make_owner(other, "Ajeno"),
    }[catalog]
    path = f"{BASE}/{catalog}/{theirs.id}"

    assert "Ajeno" not in _names(client, catalog)
    assert client.patch(path, json={_name_field(catalog): "Mío"}).status_code == 404
    assert client.delete(path).status_code == 404


def test_objectives_are_filtered_by_axis_and_by_term(client, plan):
    municipality = plan["municipality"]
    old = make_term(municipality, "Vieja", 2015, 2019)
    axis, old_axis = make_axis(municipality, plan["term"]), make_axis(municipality, old, "Viejo")
    make_objective(municipality, plan["axis"], "A")
    make_objective(municipality, axis, "B")
    make_objective(municipality, old_axis, "C")

    def names(**params):
        items = client.get(f"{BASE}/objectives", params=params).json()
        return [item["name"] for item in items]

    assert names() == ["A", "B", "C"]
    assert names(axis_id=str(axis.id)) == ["B"]
    assert names(term_id=str(plan["term"].id)) == ["A", "B"]
    assert names(term_id=str(old.id)) == ["C"]
    assert names(term_id=str(old.id), axis_id=str(axis.id)) == []


def test_axes_and_objectives_must_belong_to_something_that_exists(client, plan):
    other = make_municipality("Saira")
    term = make_term(other)
    axis = make_axis(other, term)

    for parent, catalog, field in (
        (uuid.uuid4(), "axes", "term_id"),
        (term.id, "axes", "term_id"),
        (uuid.uuid4(), "objectives", "axis_id"),
        (axis.id, "objectives", "axis_id"),
    ):
        response = client.post(f"{BASE}/{catalog}", json={field: str(parent), "name": "x"})
        assert response.status_code == 422
        assert response.json()["error"] == {
            "code": "invalid_reference",
            "message": f"{field} does not reference an existing record.",
        }


def test_an_indicator_can_be_deleted(client, plan):
    objective = make_objective(plan["municipality"], plan["axis"])
    indicator = client.post(
        f"{BASE}/indicators", json={"objective_id": str(objective.id), "name": "Cuadras"}
    ).json()
    other = make_objective(plan["municipality"], plan["axis"], "Otro")

    moved = client.patch(
        f"{BASE}/indicators/{indicator['id']}", json={"objective_id": str(other.id)}
    )
    lost = client.patch(
        f"{BASE}/indicators/{indicator['id']}", json={"objective_id": str(uuid.uuid4())}
    )
    renamed = client.patch(f"{BASE}/indicators/{indicator['id']}", json={"name": "Metros"})

    assert moved.json()["objective"] == {"id": str(other.id), "name": "Otro"}
    assert lost.json()["error"]["message"] == "objective_id does not reference an existing record."
    assert (renamed.json()["name"], renamed.json()["objective"]["name"]) == ("Metros", "Otro")
    assert client.delete(f"{BASE}/indicators/{indicator['id']}").status_code == 204
    assert client.get(f"{BASE}/indicators").json() == []
