from datetime import date

from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform.models import AuditLog
from tests.factories import login, make_membership, make_municipality, make_user
from tests.social.factories import (
    BASE,
    EMAIL,
    make_household,
    make_intervention,
    make_intervention_type,
    make_person,
    make_social_person,
    social_member,
)

SECRET = "Refiere situación de violencia en el hogar."


def _editor(client):
    municipality = social_member("editor")
    login(client, EMAIL)
    return municipality


def _items(client, **params):
    response = client.get(f"{BASE}/interventions", params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_editor_records_an_intervention(client):
    municipality = _editor(client)
    visit = make_intervention_type(municipality)
    person = make_social_person(municipality)

    response = client.post(
        f"{BASE}/interventions",
        json={
            "intervention_type_id": str(visit.id),
            "person_id": str(person.id),
            "date": "2026-03-10",
            "description": f" {SECRET} ",
            "performed_by": "Lic. Marta Ruiz",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "date": "2026-03-10",
        "intervention_type": {"id": str(visit.id), "name": "Visita a domicilio"},
        "person": {"id": str(person.id), "full_name": "Pérez, Juana"},
        "performed_by": "Lic. Marta Ruiz",
        "description": SECRET,
    }
    assert _items(client)[0]["description"] == SECRET


def test_viewer_never_receives_the_description(client):
    municipality = social_member("viewer")
    household = make_household(municipality)
    person = make_social_person(municipality, household=household)
    make_intervention(
        municipality,
        make_intervention_type(municipality),
        person,
        description=SECRET,
        performed_by="Lic. Marta Ruiz",
    )
    login(client, EMAIL)

    for params in ({}, {"person_id": str(person.id)}, {"household_id": str(household.id)}):
        response = client.get(f"{BASE}/interventions", params=params)
        assert SECRET not in response.text, params
        (item,) = response.json()["items"]
        assert item["description"] is None
        assert (item["performed_by"], item["intervention_type"]["name"]) == (
            "Lic. Marta Ruiz",
            "Visita a domicilio",
        )


def test_municipality_admin_reads_the_description_without_a_grant(client):
    municipality = make_municipality()
    make_membership(make_user(EMAIL), municipality, admin=True, enable=["social"])
    make_intervention(
        municipality,
        make_intervention_type(municipality),
        make_social_person(municipality),
        description=SECRET,
    )
    login(client, EMAIL)

    assert _items(client)[0]["description"] == SECRET


def test_intervention_references_must_belong_to_the_dashboard(client):
    other = make_municipality("Saira")
    foreign_type = make_intervention_type(other)
    foreign_person = make_social_person(other, dni="20111222")
    municipality = _editor(client)
    visit = make_intervention_type(municipality)
    person = make_social_person(municipality)
    registry_only = make_person(municipality, "Luis", "Gómez")

    def post(type_id, person_id):
        return client.post(
            f"{BASE}/interventions",
            json={
                "intervention_type_id": str(type_id),
                "person_id": str(person_id),
                "date": "2026-03-10",
            },
        )

    for response in (
        post(foreign_type.id, person.id),
        post(visit.id, foreign_person.id),
        post(visit.id, registry_only.id),
    ):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_reference"
    assert _items(client) == []


def test_interventions_are_filtered(client):
    municipality = _editor(client)
    visit = make_intervention_type(municipality)
    interview = make_intervention_type(municipality, "Entrevista")
    household = make_household(municipality)
    juana = make_social_person(municipality, household=household)
    luis = make_social_person(municipality, "Luis", "Gómez")
    make_intervention(municipality, visit, juana, on=date(2026, 3, 10))
    make_intervention(municipality, interview, juana, on=date(2025, 12, 31))
    make_intervention(municipality, visit, luis, on=date(2026, 5, 2))

    assert [(i["intervention_type"]["name"], i["date"]) for i in _items(client)] == [
        ("Visita a domicilio", "2026-05-02"),
        ("Visita a domicilio", "2026-03-10"),
        ("Entrevista", "2025-12-31"),
    ]
    assert len(_items(client, year=2026)) == 2
    assert len(_items(client, intervention_type_id=str(interview.id))) == 1
    assert len(_items(client, person_id=str(luis.id))) == 1
    assert len(_items(client, household_id=str(household.id))) == 2
    page = client.get(f"{BASE}/interventions", params={"limit": 2, "offset": 2}).json()
    assert (len(page["items"]), page["total"]) == (1, 3)


def test_editor_corrects_an_intervention_but_not_its_person_or_type(client):
    municipality = _editor(client)
    visit = make_intervention_type(municipality)
    person = make_social_person(municipality)
    other = make_social_person(municipality, "Luis", "Gómez")
    intervention = make_intervention(municipality, visit, person, description="x")

    updated = client.patch(
        f"{BASE}/interventions/{intervention.id}",
        json={"date": "2026-04-01", "description": SECRET, "performed_by": "Equipo"},
    )

    assert updated.status_code == 200
    body = updated.json()
    assert (body["date"], body["description"], body["performed_by"]) == (
        "2026-04-01",
        SECRET,
        "Equipo",
    )
    for change in ({"person_id": str(other.id)}, {"intervention_type_id": str(visit.id)}):
        response = client.patch(f"{BASE}/interventions/{intervention.id}", json=change)
        assert response.status_code == 422, change


def test_intervention_is_deleted(client):
    municipality = _editor(client)
    intervention = make_intervention(
        municipality, make_intervention_type(municipality), make_social_person(municipality)
    )

    assert client.delete(f"{BASE}/interventions/{intervention.id}").status_code == 204
    assert _items(client) == []


def test_interventions_protect_their_type_and_person(client):
    municipality = social_member("admin")
    login(client, EMAIL)
    visit = make_intervention_type(municipality)
    person = make_social_person(municipality)
    make_intervention(municipality, visit, person)

    for path in (f"intervention-types/{visit.id}", f"people/{person.id}"):
        response = client.delete(f"{BASE}/{path}")
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "in_use"


def test_viewer_cannot_change_interventions(client):
    municipality = social_member("viewer")
    visit = make_intervention_type(municipality)
    person = make_social_person(municipality)
    intervention = make_intervention(municipality, visit, person)
    login(client, EMAIL)

    body = {
        "intervention_type_id": str(visit.id),
        "person_id": str(person.id),
        "date": "2026-03-10",
    }
    assert client.post(f"{BASE}/interventions", json=body).status_code == 403
    assert (
        client.patch(
            f"{BASE}/interventions/{intervention.id}", json={"performed_by": "x"}
        ).status_code
        == 403
    )
    assert client.delete(f"{BASE}/interventions/{intervention.id}").status_code == 403


def test_interventions_of_another_municipality_are_not_reachable(client):
    other = make_municipality("Saira")
    foreign = make_intervention(
        other, make_intervention_type(other), make_social_person(other), description=SECRET
    )
    _editor(client)

    assert client.get(f"{BASE}/interventions").json() == {"items": [], "total": 0}
    assert (
        client.patch(f"{BASE}/interventions/{foreign.id}", json={"performed_by": "x"}).status_code
        == 404
    )
    assert client.delete(f"{BASE}/interventions/{foreign.id}").status_code == 404


def test_the_audit_trail_does_not_keep_the_reserved_text(client):
    municipality = _editor(client)
    body = {
        "intervention_type_id": str(make_intervention_type(municipality).id),
        "person_id": str(make_social_person(municipality).id),
        "date": "2026-03-10",
        "description": SECRET,
    }

    created = client.post(f"{BASE}/interventions", json=body).json()
    client.patch(
        f"{BASE}/interventions/{created['id']}",
        json={"description": f"{SECRET} Se deriva.", "performed_by": "Equipo"},
    )
    client.delete(f"{BASE}/interventions/{created['id']}")

    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert [e.action for e in entries] == ["create", "update", "delete"]
    assert all("violencia" not in str(e.changes) for e in entries)
    # The trail still says that the description was written and later changed.
    assert entries[0].changes["description"] == "[reserved]"
    assert entries[1].changes == {"description": "[reserved]", "performed_by": "Equipo"}


def test_interventions_are_searched_by_person_or_type_but_never_by_reserved_text(client):
    municipality = social_member("viewer")
    login(client, EMAIL)
    visit = make_intervention_type(municipality, name="Visita a domicilio")
    call = make_intervention_type(municipality, name="Llamado")
    juana = make_social_person(municipality, "Juana", "Pérez", dni="20123456")
    luis = make_social_person(municipality, "Luis", "Gómez")
    make_intervention(municipality, visit, juana, description="Situación de violencia")
    make_intervention(municipality, call, luis)

    def types(q):
        return [item["intervention_type"]["name"] for item in _items(client, q=q)]

    assert types("perez") == ["Visita a domicilio"]
    assert types("20.123.456") == ["Visita a domicilio"]
    assert types("llamado") == ["Llamado"]
    # The reserved text cannot be probed through the search.
    assert types("violencia") == []


def test_the_audit_trail_keeps_everything_but_the_reserved_text(client):
    municipality = _editor(client)
    person = make_social_person(municipality)
    intervention = make_intervention(
        municipality, make_intervention_type(municipality), person, description="Reservado"
    )
    path = f"{BASE}/interventions/{intervention.id}"

    client.patch(path, json={"performed_by": "Ana"})
    client.patch(path, json={"performed_by": "Luis", "description": "Muy reservado"})

    with tenant_session(municipality.id) as db:
        changes = db.scalars(select(AuditLog.changes).order_by(AuditLog.created_at)).all()
    assert changes == [
        {"performed_by": "Ana"},
        {"performed_by": "Luis", "description": "[reserved]"},
    ]
