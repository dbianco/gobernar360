"""PATCH changes what it is sent and nothing else, in every dashboard."""

import uuid

from sqlalchemy import func, select

from gobernar360.core.db import tenant_session
from gobernar360.platform.models import AuditLog
from tests.economic.factories import (
    economic_member,
    make_economic_person,
    make_tool,
    make_tool_category,
    make_tool_subcategory,
)
from tests.environment.factories import environment_member, make_subcategory, make_variable
from tests.factories import login, make_municipality
from tests.social.factories import make_social_person, social_member

EMAIL = "ana@noetinger.test"


def _audited(municipality) -> int:
    with tenant_session(municipality.id) as db:
        return db.scalar(select(func.count()).select_from(AuditLog))


def test_a_tool_keeps_its_subcategory_only_inside_its_category(client):
    municipality = economic_member("admin")
    category, other = make_tool_category(municipality), make_tool_category(municipality, "Empleo")
    subcategory = make_tool_subcategory(municipality, category)
    tool = make_tool(municipality, category, subcategory_id=subcategory.id)
    login(client, EMAIL)
    path = f"/api/dashboards/economic/tools/{tool.id}"

    renamed = client.patch(path, json={"name": "Otra"}).json()
    same = client.patch(path, json={"category_id": str(category.id)}).json()
    moved = client.patch(path, json={"category_id": str(other.id)}).json()

    assert (renamed["name"], renamed["subcategory"]["id"]) == ("Otra", str(subcategory.id))
    assert same["subcategory"]["id"] == str(subcategory.id)
    assert (moved["category"]["id"], moved["subcategory"]) == (str(other.id), None)


def test_an_economic_person_changes_by_parts(client):
    municipality = economic_member("editor")
    person = make_economic_person(municipality, "Juana", "Pérez", occupation="Tejedora")
    login(client, EMAIL)
    path = f"/api/dashboards/economic/people/{person.id}"

    nothing = client.patch(path, json={}).json()
    audited = _audited(municipality)
    own = client.patch(path, json={"occupation": "Panadera"}).json()
    common = client.patch(path, json={"person": {"first_name": "Juana María"}}).json()

    assert (nothing["occupation"], nothing["person"]["first_name"]) == ("Tejedora", "Juana")
    assert audited == 0
    assert (own["occupation"], own["person"]["first_name"]) == ("Panadera", "Juana")
    assert (common["occupation"], common["person"]["first_name"]) == ("Panadera", "Juana María")


def test_a_social_person_changes_by_parts(client):
    municipality = social_member("editor")
    person = make_social_person(municipality, "Juana", "Pérez", phone="1")
    login(client, EMAIL)
    path = f"/api/dashboards/social/people/{person.id}"

    for body in ({}, {"person": {}}):
        assert client.patch(path, json=body).json()["person"]["phone"] == "1"
    assert _audited(municipality) == 0
    changed = client.patch(path, json={"person": {"phone": "2"}}).json()
    assert (changed["person"]["phone"], changed["person"]["first_name"]) == ("2", "Juana")
    assert client.get(path).json() == changed


def test_social_people_are_found_by_name_document_and_neighborhood(client):
    municipality = social_member("viewer")
    make_social_person(municipality, "Juana", "Gómez", dni="20123456", neighborhood="Barrio Norte")
    make_social_person(municipality, "Luis", "Sosa", dni="30999888", neighborhood="Sur")
    make_social_person(make_municipality("Saira"), "Juana", "Ajena", dni="20123456")
    login(client, EMAIL)

    def found(**params):
        items = client.get("/api/dashboards/social/people", params=params).json()["items"]
        return [item["person"]["last_name"] for item in items]

    assert found() == ["Gómez", "Sosa"]
    assert found(q="juana gomez") == ["Gómez"]
    assert found(q="juana sosa") == []
    # Documents with dots too, and parts of them; but not as a name.
    assert found(q="20.123.456") == found(q="123456") == ["Gómez"]
    assert found(q="sosa 999") == ["Sosa"]
    assert found(neighborhood=" norte ") == ["Gómez"]
    assert found(neighborhood="   ") == ["Gómez", "Sosa"]
    assert found(q="luis", neighborhood="norte") == []


def test_a_variable_moves_to_another_subcategory_only_if_it_exists(client):
    municipality = environment_member("admin")
    variable = make_variable(municipality, make_subcategory(municipality))
    other = make_subcategory(municipality, name="Otra")
    login(client, EMAIL)
    path = f"/api/dashboards/environment/variables/{variable.id}"

    renamed = client.patch(path, json={"name": "Nueva"})
    moved = client.patch(path, json={"subcategory_id": str(other.id)})
    lost = client.patch(path, json={"subcategory_id": str(uuid.uuid4())})

    assert renamed.json()["name"] == "Nueva"
    assert moved.json()["subcategory"]["id"] == str(other.id)
    assert lost.status_code == 422
    assert (
        lost.json()["error"]["message"] == "subcategory_id does not reference an existing record."
    )


def test_a_partial_update_is_an_object(client):
    municipality = social_member("editor")
    person = make_social_person(municipality)
    login(client, EMAIL)

    for body in ([], "x", 3, None):
        response = client.patch(f"/api/dashboards/social/people/{person.id}", json=body)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
