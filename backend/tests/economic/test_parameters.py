import uuid

import pytest
from sqlalchemy import select, text

from gobernar360.core.db import get_admin_engine, tenant_session
from gobernar360.platform.models import AuditLog
from tests.economic.factories import (
    BASE,
    EMAIL,
    economic_member,
    make_actor,
    make_actor_type,
    make_assignment,
    make_sector,
    make_tool,
    make_tool_category,
    make_tool_subcategory,
)
from tests.factories import login, make_municipality

CATALOGS = ["actor-types", "sectors", "tool-categories"]


def _admin(client):
    municipality = economic_member("admin")
    login(client, EMAIL)
    return municipality


@pytest.mark.parametrize("catalog", CATALOGS)
def test_dashboard_admin_manages_each_catalog(client, catalog):
    _admin(client)

    second = client.post(f"{BASE}/{catalog}", json={"name": "  Servicios  "})
    first = client.post(f"{BASE}/{catalog}", json={"name": "Agro"})
    renamed = client.patch(f"{BASE}/{catalog}/{first.json()['id']}", json={"name": "Agroindustria"})

    assert (second.status_code, first.status_code, renamed.status_code) == (201, 201, 200)
    assert [item["name"] for item in client.get(f"{BASE}/{catalog}").json()] == [
        "Agroindustria",
        "Servicios",
    ]
    assert client.post(f"{BASE}/{catalog}", json={"name": "   "}).status_code == 422
    assert client.delete(f"{BASE}/{catalog}/{second.json()['id']}").status_code == 204
    assert len(client.get(f"{BASE}/{catalog}").json()) == 1


def test_subcategory_belongs_to_a_category(client):
    municipality = _admin(client)
    category = make_tool_category(municipality)
    other = make_tool_category(municipality, "Capacitación")

    created = client.post(
        f"{BASE}/tool-subcategories", json={"category_id": str(category.id), "name": "Créditos"}
    )
    client.post(f"{BASE}/tool-subcategories", json={"category_id": str(other.id), "name": "Cursos"})

    assert created.status_code == 201
    assert created.json() == {
        "id": created.json()["id"],
        "category_id": str(category.id),
        "name": "Créditos",
    }
    assert [s["name"] for s in client.get(f"{BASE}/tool-subcategories").json()] == [
        "Créditos",
        "Cursos",
    ]
    renamed = client.patch(
        f"{BASE}/tool-subcategories/{created.json()['id']}", json={"name": "Microcréditos"}
    )
    assert renamed.json()["name"] == "Microcréditos"
    moved = client.patch(
        f"{BASE}/tool-subcategories/{created.json()['id']}", json={"category_id": str(other.id)}
    )
    assert moved.status_code == 422


def test_tool_is_created_listed_and_updated(client):
    municipality = _admin(client)
    category = make_tool_category(municipality)
    subcategory = make_tool_subcategory(municipality, category)

    created = client.post(
        f"{BASE}/tools",
        json={
            "category_id": str(category.id),
            "subcategory_id": str(subcategory.id),
            "name": " Microcrédito productivo ",
            "description": "Hasta $ 500.000 a tasa cero.",
            "audience": "actors",
        },
    )
    simple = client.post(f"{BASE}/tools", json={"category_id": str(category.id), "name": "Aval"})

    assert (created.status_code, simple.status_code) == (201, 201)
    assert created.json() == {
        "id": created.json()["id"],
        "name": "Microcrédito productivo",
        "description": "Hasta $ 500.000 a tasa cero.",
        "audience": "actors",
        "category": {"id": str(category.id), "name": "Financiamiento"},
        "subcategory": {"id": str(subcategory.id), "name": "Microcréditos"},
    }
    assert (simple.json()["audience"], simple.json()["subcategory"]) == ("both", None)
    assert [tool["name"] for tool in client.get(f"{BASE}/tools").json()] == [
        "Aval",
        "Microcrédito productivo",
    ]

    updated = client.patch(
        f"{BASE}/tools/{created.json()['id']}",
        json={"name": "Microcrédito", "subcategory_id": None, "audience": "people"},
    )

    assert updated.status_code == 200
    body = updated.json()
    assert (body["name"], body["subcategory"], body["audience"]) == ("Microcrédito", None, "people")
    assert body["description"] == "Hasta $ 500.000 a tasa cero."


def test_tool_subcategory_must_belong_to_its_category(client):
    municipality = _admin(client)
    category = make_tool_category(municipality)
    other = make_tool_category(municipality, "Capacitación")
    foreign_subcategory = make_tool_subcategory(municipality, other, "Cursos")
    tool = make_tool(municipality, category)

    created = client.post(
        f"{BASE}/tools",
        json={
            "category_id": str(category.id),
            "subcategory_id": str(foreign_subcategory.id),
            "name": "x",
        },
    )
    patched = client.patch(
        f"{BASE}/tools/{tool.id}", json={"subcategory_id": str(foreign_subcategory.id)}
    )
    moved = client.patch(
        f"{BASE}/tools/{tool.id}",
        json={"category_id": str(other.id), "subcategory_id": str(foreign_subcategory.id)},
    )

    assert (created.status_code, patched.status_code, moved.status_code) == (422, 422, 200)
    assert (
        created.json()["error"]
        == patched.json()["error"]
        == {
            "code": "invalid_reference",
            "message": "subcategory_id does not belong to the tool's category.",
        }
    )


def test_changing_the_category_of_a_tool_drops_a_subcategory_of_the_old_one(client):
    municipality = _admin(client)
    category = make_tool_category(municipality)
    subcategory = make_tool_subcategory(municipality, category)
    other = make_tool_category(municipality, "Capacitación")
    tool = make_tool(municipality, category, subcategory_id=subcategory.id)

    moved = client.patch(f"{BASE}/tools/{tool.id}", json={"category_id": str(other.id)})

    assert moved.status_code == 200
    assert (moved.json()["category"]["name"], moved.json()["subcategory"]) == ("Capacitación", None)


def test_tool_cannot_reference_parameters_of_another_municipality(client):
    other = make_municipality("Saira")
    foreign_category = make_tool_category(other)
    municipality = _admin(client)
    tool = make_tool(municipality)

    created = client.post(
        f"{BASE}/tools", json={"category_id": str(foreign_category.id), "name": "x"}
    )
    moved = client.patch(f"{BASE}/tools/{tool.id}", json={"category_id": str(foreign_category.id)})
    subcategory = client.post(
        f"{BASE}/tool-subcategories", json={"category_id": str(foreign_category.id), "name": "x"}
    )

    assert (created.status_code, moved.status_code, subcategory.status_code) == (422, 422, 422)
    assert created.json()["error"] == {
        "code": "invalid_reference",
        "message": "category_id does not reference an existing record.",
    }


def test_a_tool_cannot_name_a_subcategory_that_does_not_exist(client):
    municipality = _admin(client)
    category = make_tool_category(municipality)

    created = client.post(
        f"{BASE}/tools",
        json={"category_id": str(category.id), "subcategory_id": str(uuid.uuid4()), "name": "x"},
    )

    assert created.json()["error"] == {
        "code": "invalid_reference",
        "message": "subcategory_id does not reference an existing record.",
    }


def test_unknown_audience_is_rejected(client):
    municipality = _admin(client)
    category = make_tool_category(municipality)

    response = client.post(
        f"{BASE}/tools", json={"category_id": str(category.id), "name": "x", "audience": "all"}
    )

    assert response.status_code == 422


def test_editor_cannot_change_parameters(client):
    municipality = economic_member("editor")
    category = make_tool_category(municipality)
    tool = make_tool(municipality, category)
    login(client, EMAIL)

    for catalog in CATALOGS:
        assert client.post(f"{BASE}/{catalog}", json={"name": "x"}).status_code == 403
    assert (
        client.post(
            f"{BASE}/tools", json={"category_id": str(category.id), "name": "x"}
        ).status_code
        == 403
    )
    assert client.patch(f"{BASE}/tools/{tool.id}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{BASE}/tools/{tool.id}").status_code == 403
    assert client.delete(f"{BASE}/tool-categories/{category.id}").status_code == 403


def test_viewer_lists_parameters(client):
    municipality = economic_member("viewer")
    make_actor_type(municipality)
    make_sector(municipality)
    category = make_tool_category(municipality)
    make_tool_subcategory(municipality, category)
    make_tool(municipality, category)
    login(client, EMAIL)

    assert [i["name"] for i in client.get(f"{BASE}/actor-types").json()] == ["Comercio"]
    assert [i["name"] for i in client.get(f"{BASE}/sectors").json()] == ["Alimentos"]
    assert len(client.get(f"{BASE}/tool-categories").json()) == 1
    assert len(client.get(f"{BASE}/tool-subcategories").json()) == 1
    assert len(client.get(f"{BASE}/tools").json()) == 1


def test_member_without_grant_is_rejected(client):
    economic_member(None)
    login(client, EMAIL)

    for path in ("actor-types", "sectors", "tool-categories", "tool-subcategories", "tools"):
        assert client.get(f"{BASE}/{path}").status_code == 403, path


def test_parameters_of_another_municipality_are_not_listed_nor_editable(client):
    other = make_municipality("Saira")
    foreign_type = make_actor_type(other)
    foreign_tool = make_tool(other)
    _admin(client)

    assert client.get(f"{BASE}/actor-types").json() == []
    assert client.get(f"{BASE}/tools").json() == []
    assert (
        client.patch(f"{BASE}/actor-types/{foreign_type.id}", json={"name": "x"}).status_code == 404
    )
    assert client.delete(f"{BASE}/actor-types/{foreign_type.id}").status_code == 404
    assert client.patch(f"{BASE}/tools/{foreign_tool.id}", json={"name": "x"}).status_code == 404
    assert client.delete(f"{BASE}/tools/{foreign_tool.id}").status_code == 404


def test_deleting_parameters_in_use_returns_in_use(client):
    municipality = _admin(client)
    actor_type, sector = make_actor_type(municipality), make_sector(municipality)
    actor = make_actor(municipality, actor_type_id=actor_type.id, sector_id=sector.id)
    category = make_tool_category(municipality)
    subcategory = make_tool_subcategory(municipality, category)
    tool = make_tool(municipality, category, subcategory_id=subcategory.id)
    make_assignment(municipality, tool, actor=actor)

    for path in (
        f"actor-types/{actor_type.id}",
        f"sectors/{sector.id}",
        f"tool-categories/{category.id}",
        f"tool-subcategories/{subcategory.id}",
        f"tools/{tool.id}",
    ):
        response = client.delete(f"{BASE}/{path}")
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "in_use"
    assert len(client.get(f"{BASE}/tools").json()) == 1


def test_parameter_change_is_audited(client):
    municipality = _admin(client)

    sector_id = client.post(f"{BASE}/sectors", json={"name": "Turismo"}).json()["id"]
    client.patch(f"{BASE}/sectors/{sector_id}", json={"name": "Turismo rural"})
    client.delete(f"{BASE}/sectors/{sector_id}")

    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert [(e.action, e.entity_type) for e in entries] == [
        ("create", "economic_sectors"),
        ("update", "economic_sectors"),
        ("delete", "economic_sectors"),
    ]
    assert entries[1].changes == {"name": "Turismo rural"}


def test_every_economic_table_enforces_tenant_isolation():
    with get_admin_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                "EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid "
                "AND p.polname = 'tenant_isolation') "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' "
                "AND c.relname LIKE 'economic\\_%'"
            )
        ).all()

    assert sorted(row[0] for row in rows) == [
        "economic_actor_people",
        "economic_actor_types",
        "economic_actors",
        "economic_assignments",
        "economic_people",
        "economic_sectors",
        "economic_tool_categories",
        "economic_tool_subcategories",
        "economic_tools",
    ]
    assert all(row[1] and row[2] and row[3] for row in rows)


def test_a_tool_keeps_its_subcategory_unless_its_category_changes(client):
    municipality = economic_member("admin")
    login(client, EMAIL)
    credit, training = (make_tool_category(municipality, n) for n in ("Crédito", "Formación"))
    micro = make_tool_subcategory(municipality, credit, "Micro")
    tool = make_tool(municipality, credit, subcategory_id=micro.id)
    url = f"{BASE}/tools/{tool.id}"

    same = client.patch(url, json={"category_id": str(credit.id)}).json()
    assert same["subcategory"]["id"] == str(micro.id)
    moved = client.patch(url, json={"category_id": str(training.id)}).json()
    assert (moved["category"]["id"], moved["subcategory"]) == (str(training.id), None)
