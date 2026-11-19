from datetime import date

from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform.models import AuditLog
from tests.factories import login, make_municipality
from tests.social.factories import (
    BASE,
    EMAIL,
    make_benefit,
    make_benefit_category,
    make_delivery,
    make_household,
    make_person,
    make_social_person,
    social_member,
)


def _editor(client):
    municipality = social_member("editor")
    login(client, EMAIL)
    return municipality


def _benefits(client, **params):
    response = client.get(f"{BASE}/deliveries", params=params)
    assert response.status_code == 200, response.text
    return [(item["benefit"]["name"], item["date"]) for item in response.json()["items"]]


def test_editor_records_a_delivery(client):
    municipality = _editor(client)
    benefit = make_benefit(municipality)
    person = make_social_person(municipality)

    response = client.post(
        f"{BASE}/deliveries",
        json={
            "benefit_id": str(benefit.id),
            "person_id": str(person.id),
            "date": "2026-03-10",
            "quantity": 3,
            "note": " Retira la hija ",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "date": "2026-03-10",
        "quantity": 3,
        "note": "Retira la hija",
        "benefit": {
            "id": str(benefit.id),
            "name": "Módulo alimentario",
            "category": {"id": str(benefit.category_id), "name": "Alimentos"},
        },
        "person": {"id": str(person.id), "full_name": "Pérez, Juana"},
    }
    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog)).all()
    assert [(e.action, e.entity_type) for e in entries] == [("create", "social_deliveries")]


def test_quantity_defaults_to_one_and_must_be_positive(client):
    municipality = _editor(client)
    body = {
        "benefit_id": str(make_benefit(municipality).id),
        "person_id": str(make_social_person(municipality).id),
        "date": "2026-03-10",
    }

    assert client.post(f"{BASE}/deliveries", json=body).json()["quantity"] == 1
    for quantity in (0, -1, 1.5, 1_000_001):
        response = client.post(f"{BASE}/deliveries", json=body | {"quantity": quantity})
        assert response.status_code == 422, quantity
    assert client.post(f"{BASE}/deliveries", json=body | {"date": "tomorrow"}).status_code == 422


def test_delivery_references_must_belong_to_the_dashboard(client):
    other = make_municipality("Saira")
    foreign_benefit = make_benefit(other)
    foreign_person = make_social_person(other, dni="20111222")
    municipality = _editor(client)
    benefit = make_benefit(municipality)
    person = make_social_person(municipality)
    registry_only = make_person(municipality, "Luis", "Gómez")

    def post(benefit_id, person_id):
        return client.post(
            f"{BASE}/deliveries",
            json={"benefit_id": str(benefit_id), "person_id": str(person_id), "date": "2026-03-10"},
        )

    for response in (
        post(foreign_benefit.id, person.id),
        post(benefit.id, foreign_person.id),
        post(benefit.id, registry_only.id),
    ):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_reference"
    assert client.get(f"{BASE}/deliveries").json()["total"] == 0


def test_deliveries_are_filtered(client):
    municipality = _editor(client)
    food = make_benefit_category(municipality)
    housing = make_benefit_category(municipality, "Hábitat")
    box = make_benefit(municipality, food)
    sheets = make_benefit(municipality, housing, "Chapas")
    household = make_household(municipality)
    juana = make_social_person(municipality, household=household)
    luis = make_social_person(municipality, "Luis", "Gómez")
    make_delivery(municipality, box, juana, on=date(2026, 3, 10))
    make_delivery(municipality, sheets, juana, on=date(2025, 12, 31))
    make_delivery(municipality, box, luis, on=date(2026, 5, 2))

    assert _benefits(client) == [
        ("Módulo alimentario", "2026-05-02"),
        ("Módulo alimentario", "2026-03-10"),
        ("Chapas", "2025-12-31"),
    ]
    assert len(_benefits(client, year=2026)) == 2
    assert _benefits(client, benefit_id=str(sheets.id)) == [("Chapas", "2025-12-31")]
    assert _benefits(client, category_id=str(housing.id)) == [("Chapas", "2025-12-31")]
    assert len(_benefits(client, person_id=str(luis.id))) == 1
    assert len(_benefits(client, household_id=str(household.id))) == 2
    assert _benefits(client, household_id=str(household.id), year=2026) == [
        ("Módulo alimentario", "2026-03-10")
    ]
    page = client.get(f"{BASE}/deliveries", params={"limit": 1, "offset": 2}).json()
    assert (len(page["items"]), page["total"]) == (1, 3)


def test_editor_corrects_a_delivery_but_not_who_received_what(client):
    municipality = _editor(client)
    benefit = make_benefit(municipality)
    person = make_social_person(municipality)
    other = make_social_person(municipality, "Luis", "Gómez")
    delivery = make_delivery(municipality, benefit, person, note="x")

    updated = client.patch(
        f"{BASE}/deliveries/{delivery.id}", json={"date": "2026-04-01", "quantity": 2}
    )

    assert updated.status_code == 200
    body = updated.json()
    assert (body["date"], body["quantity"], body["note"]) == ("2026-04-01", 2, "x")
    for change in ({"person_id": str(other.id)}, {"benefit_id": str(benefit.id)}, {"quantity": 0}):
        response = client.patch(f"{BASE}/deliveries/{delivery.id}", json=change)
        assert response.status_code == 422, change


def test_delivery_is_deleted(client):
    municipality = _editor(client)
    delivery = make_delivery(
        municipality, make_benefit(municipality), make_social_person(municipality)
    )

    assert client.delete(f"{BASE}/deliveries/{delivery.id}").status_code == 204
    assert client.get(f"{BASE}/deliveries").json()["total"] == 0


def test_records_in_use_protect_benefit_and_person(client):
    municipality = social_member("admin")
    login(client, EMAIL)
    benefit = make_benefit(municipality)
    person = make_social_person(municipality)
    make_delivery(municipality, benefit, person)

    for path in (f"benefits/{benefit.id}", f"people/{person.id}"):
        response = client.delete(f"{BASE}/{path}")
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "in_use"
    assert client.get(f"{BASE}/people/{person.id}").status_code == 200


def test_viewer_reads_deliveries_but_cannot_change_them(client):
    municipality = social_member("viewer")
    benefit = make_benefit(municipality)
    person = make_social_person(municipality)
    delivery = make_delivery(municipality, benefit, person)
    login(client, EMAIL)

    assert client.get(f"{BASE}/deliveries").json()["total"] == 1
    body = {"benefit_id": str(benefit.id), "person_id": str(person.id), "date": "2026-03-10"}
    assert client.post(f"{BASE}/deliveries", json=body).status_code == 403
    assert client.patch(f"{BASE}/deliveries/{delivery.id}", json={"note": "x"}).status_code == 403
    assert client.delete(f"{BASE}/deliveries/{delivery.id}").status_code == 403


def test_deliveries_of_another_municipality_are_not_reachable(client):
    other = make_municipality("Saira")
    foreign = make_delivery(other, make_benefit(other), make_social_person(other))
    _editor(client)

    assert client.get(f"{BASE}/deliveries").json() == {"items": [], "total": 0}
    assert client.patch(f"{BASE}/deliveries/{foreign.id}", json={"note": "x"}).status_code == 404
    assert client.delete(f"{BASE}/deliveries/{foreign.id}").status_code == 404
