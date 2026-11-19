import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from gobernar360.core.db import get_admin_engine, tenant_session
from gobernar360.platform.models import AuditLog
from tests.factories import login, make_municipality
from tests.social.factories import (
    BASE,
    EMAIL,
    make_benefit,
    make_benefit_category,
    make_delivery,
    make_household,
    make_intervention,
    make_intervention_type,
    make_social_person,
    social_member,
)

CATALOGS = ["benefit-categories", "intervention-types"]


def _admin(client):
    municipality = social_member("admin")
    login(client, EMAIL)
    return municipality


@pytest.mark.parametrize("catalog", CATALOGS)
def test_dashboard_admin_manages_each_catalog(client, catalog):
    _admin(client)

    second = client.post(f"{BASE}/{catalog}", json={"name": "  Vivienda  "})
    first = client.post(f"{BASE}/{catalog}", json={"name": "Abrigo"})
    renamed = client.patch(f"{BASE}/{catalog}/{first.json()['id']}", json={"name": "Abrigos"})

    assert (second.status_code, first.status_code, renamed.status_code) == (201, 201, 200)
    assert [item["name"] for item in client.get(f"{BASE}/{catalog}").json()] == [
        "Abrigos",
        "Vivienda",
    ]
    assert client.post(f"{BASE}/{catalog}", json={"name": "   "}).status_code == 422
    assert client.delete(f"{BASE}/{catalog}/{second.json()['id']}").status_code == 204
    assert len(client.get(f"{BASE}/{catalog}").json()) == 1


def test_benefit_is_created_listed_and_updated(client):
    municipality = _admin(client)
    category = make_benefit_category(municipality)
    other = make_benefit_category(municipality, "Hábitat")

    created = client.post(
        f"{BASE}/benefits",
        json={
            "category_id": str(category.id),
            "name": " Módulo alimentario ",
            "description": "Caja mensual.",
        },
    )
    simple = client.post(f"{BASE}/benefits", json={"category_id": str(other.id), "name": "Chapas"})

    assert (created.status_code, simple.status_code) == (201, 201)
    assert created.json() == {
        "id": created.json()["id"],
        "name": "Módulo alimentario",
        "description": "Caja mensual.",
        "category": {"id": str(category.id), "name": "Alimentos"},
    }
    assert [b["name"] for b in client.get(f"{BASE}/benefits").json()] == [
        "Chapas",
        "Módulo alimentario",
    ]

    updated = client.patch(
        f"{BASE}/benefits/{created.json()['id']}",
        json={"name": "Módulo", "category_id": str(other.id)},
    )

    assert updated.status_code == 200
    body = updated.json()
    assert (body["name"], body["category"]["name"], body["description"]) == (
        "Módulo",
        "Hábitat",
        "Caja mensual.",
    )


def test_benefit_cannot_reference_a_category_of_another_municipality(client):
    other = make_municipality("Saira")
    foreign_category = make_benefit_category(other)
    municipality = _admin(client)
    benefit = make_benefit(municipality)

    created = client.post(
        f"{BASE}/benefits", json={"category_id": str(foreign_category.id), "name": "x"}
    )
    moved = client.patch(
        f"{BASE}/benefits/{benefit.id}", json={"category_id": str(foreign_category.id)}
    )

    assert (created.status_code, moved.status_code) == (422, 422)
    assert created.json()["error"]["code"] == "invalid_reference"


def test_editor_cannot_change_parameters(client):
    municipality = social_member("editor")
    category = make_benefit_category(municipality)
    benefit = make_benefit(municipality, category)
    login(client, EMAIL)

    for catalog in CATALOGS:
        assert client.post(f"{BASE}/{catalog}", json={"name": "x"}).status_code == 403
    assert (
        client.post(
            f"{BASE}/benefits", json={"category_id": str(category.id), "name": "x"}
        ).status_code
        == 403
    )
    assert client.patch(f"{BASE}/benefits/{benefit.id}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{BASE}/benefits/{benefit.id}").status_code == 403
    assert client.delete(f"{BASE}/benefit-categories/{category.id}").status_code == 403


def test_viewer_lists_parameters(client):
    municipality = social_member("viewer")
    make_benefit(municipality)
    make_intervention_type(municipality)
    login(client, EMAIL)

    assert [i["name"] for i in client.get(f"{BASE}/benefit-categories").json()] == ["Alimentos"]
    assert [i["name"] for i in client.get(f"{BASE}/intervention-types").json()] == [
        "Visita a domicilio"
    ]
    assert len(client.get(f"{BASE}/benefits").json()) == 1


def test_member_without_grant_is_rejected(client):
    social_member(None)
    login(client, EMAIL)

    for path in ("benefit-categories", "intervention-types", "benefits"):
        assert client.get(f"{BASE}/{path}").status_code == 403, path


def test_parameters_of_another_municipality_are_not_listed_nor_editable(client):
    other = make_municipality("Saira")
    foreign_type = make_intervention_type(other)
    foreign_benefit = make_benefit(other)
    _admin(client)

    assert client.get(f"{BASE}/intervention-types").json() == []
    assert client.get(f"{BASE}/benefits").json() == []
    assert (
        client.patch(f"{BASE}/intervention-types/{foreign_type.id}", json={"name": "x"}).status_code
        == 404
    )
    assert client.delete(f"{BASE}/intervention-types/{foreign_type.id}").status_code == 404
    assert (
        client.patch(f"{BASE}/benefits/{foreign_benefit.id}", json={"name": "x"}).status_code == 404
    )
    assert client.delete(f"{BASE}/benefits/{foreign_benefit.id}").status_code == 404


def test_deleting_parameters_in_use_returns_in_use(client):
    municipality = _admin(client)
    category = make_benefit_category(municipality)
    benefit = make_benefit(municipality, category)
    intervention_type = make_intervention_type(municipality)
    person = make_social_person(municipality)
    make_delivery(municipality, benefit, person)
    make_intervention(municipality, intervention_type, person)

    for path in (
        f"benefit-categories/{category.id}",
        f"benefits/{benefit.id}",
        f"intervention-types/{intervention_type.id}",
    ):
        response = client.delete(f"{BASE}/{path}")
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "in_use"
    assert len(client.get(f"{BASE}/benefits").json()) == 1


def test_parameter_change_is_audited(client):
    municipality = _admin(client)

    type_id = client.post(f"{BASE}/intervention-types", json={"name": "Entrevista"}).json()["id"]
    client.patch(f"{BASE}/intervention-types/{type_id}", json={"name": "Entrevista telefónica"})
    client.delete(f"{BASE}/intervention-types/{type_id}")

    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert [(e.action, e.entity_type) for e in entries] == [
        ("create", "social_intervention_types"),
        ("update", "social_intervention_types"),
        ("delete", "social_intervention_types"),
    ]
    assert entries[1].changes == {"name": "Entrevista telefónica"}


def test_every_social_table_enforces_tenant_isolation():
    with get_admin_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                "EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid "
                "AND p.polname = 'tenant_isolation') "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' "
                "AND c.relname LIKE 'social\\_%'"
            )
        ).all()

    assert sorted(row[0] for row in rows) == [
        "social_benefit_categories",
        "social_benefits",
        "social_deliveries",
        "social_households",
        "social_intervention_types",
        "social_interventions",
        "social_people",
    ]
    assert all(row[1] and row[2] and row[3] for row in rows)


def test_a_household_has_at_most_one_head():
    municipality = make_municipality()
    household = make_household(municipality)
    make_social_person(municipality, household=household, relationship="head", dni="20111222")

    with pytest.raises(IntegrityError):
        make_social_person(municipality, "Luis", household=household, relationship="head")
