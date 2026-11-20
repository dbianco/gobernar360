import pytest
from sqlalchemy import func, select

from gobernar360.core.db import tenant_session
from gobernar360.dashboards.procedures.models import ProcedureRequirement
from tests.factories import make_municipality
from tests.procedures.factories import (
    BASE,
    link_requirement,
    make_area,
    make_procedure,
    make_requirement,
    make_source,
    signed_in,
)

URL = f"{BASE}/procedures"


def _names(response):
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()["items"]]


def test_editor_creates_a_procedure_with_only_a_name_and_an_area(client):
    municipality = signed_in(client)
    area = make_area(municipality)

    response = client.post(URL, json={"name": " Habilitación comercial ", "area_id": str(area.id)})

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "name": "Habilitación comercial",
        "description": "",
        "area": {"id": str(area.id), "name": "Rentas"},
        "audience": "both",
        "channel": "in_person",
        "url": "",
        "is_free": True,
        "cost": None,
        "duration_days": None,
        "annual_volume": None,
        "is_active": True,
        "requirement_count": 0,
    }


def test_editor_creates_a_procedure_with_every_field(client):
    municipality = signed_in(client)
    area = make_area(municipality)
    payload = {
        "name": "Licencia de conducir",
        "description": "Primera licencia y renovaciones.",
        "area_id": str(area.id),
        "audience": "people",
        "channel": "both",
        "url": "https://noetinger.example/licencias",
        "is_free": False,
        "cost": "15000.50",
        "duration_days": 7,
        "annual_volume": 1200,
        "is_active": False,
    }

    response = client.post(URL, json=payload)

    assert response.status_code == 201
    body = response.json()
    assert {key: body[key] for key in payload if key != "area_id"} == {
        key: value for key, value in payload.items() if key != "area_id"
    }


@pytest.mark.parametrize(
    "fields",
    [
        {"is_free": True, "cost": "100"},
        {"is_free": False, "cost": "-1"},
        {"duration_days": -1},
        {"annual_volume": -5},
        {"audience": "martians"},
        {"channel": "fax"},
        {"url": "javascript:alert(1)"},
        {"url": "noetinger.example"},
        {"name": " "},
    ],
)
def test_invalid_procedures_are_rejected(client, fields):
    municipality = signed_in(client)
    area = make_area(municipality)

    response = client.post(URL, json={"name": "Trámite", "area_id": str(area.id)} | fields)

    assert response.status_code == 422, response.text


def test_making_a_procedure_free_clears_its_cost(client):
    municipality = signed_in(client)
    procedure = make_procedure(municipality, is_free=False, cost=500)

    patched = client.patch(f"{URL}/{procedure.id}", json={"is_free": True})
    priced_while_free = client.patch(f"{URL}/{procedure.id}", json={"cost": "10"})

    assert patched.status_code == 200
    assert (patched.json()["is_free"], patched.json()["cost"]) == (True, None)
    assert priced_while_free.status_code == 422


def test_editor_updates_and_deletes_a_procedure(client):
    municipality = signed_in(client)
    procedure = make_procedure(municipality)
    other_area = make_area(municipality, "Tránsito")
    link_requirement(procedure, make_requirement(municipality))

    patched = client.patch(
        f"{URL}/{procedure.id}",
        json={"name": "Habilitación", "area_id": str(other_area.id), "duration_days": None},
    )

    assert patched.status_code == 200
    assert (patched.json()["name"], patched.json()["area"]["name"]) == ("Habilitación", "Tránsito")
    assert patched.json()["requirement_count"] == 1
    assert client.patch(f"{URL}/{procedure.id}", json={"name": None}).status_code == 422
    assert client.delete(f"{URL}/{procedure.id}").status_code == 204
    assert client.get(f"{URL}/{procedure.id}").status_code == 404
    with tenant_session(municipality.id) as db:
        assert db.scalar(select(func.count()).select_from(ProcedureRequirement)) == 0


def test_viewer_reads_but_cannot_write(client):
    municipality = signed_in(client, "viewer")
    procedure = make_procedure(municipality)
    requirement = make_requirement(municipality)
    link = link_requirement(procedure, make_requirement(municipality, "DNI"))

    assert _names(client.get(URL)) == ["Habilitación comercial"]
    assert client.get(f"{URL}/{procedure.id}").status_code == 200
    assert (
        client.post(URL, json={"name": "x", "area_id": str(procedure.area_id)}).status_code == 403
    )
    assert client.patch(f"{URL}/{procedure.id}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{URL}/{procedure.id}").status_code == 403
    links = f"{URL}/{procedure.id}/requirements"
    assert client.post(links, json={"requirement_id": str(requirement.id)}).status_code == 403
    assert client.patch(f"{links}/{link.id}", json={"mandatory": False}).status_code == 403
    assert client.delete(f"{links}/{link.id}").status_code == 403


def test_procedures_are_filtered_searched_and_paged(client):
    municipality = signed_in(client, "viewer")
    rentas, obras = make_area(municipality, "Rentas"), make_area(municipality, "Obras")
    make_procedure(municipality, rentas, "Exención de tasas", channel="online")
    make_procedure(municipality, rentas, "Libre deuda", channel="both")
    make_procedure(municipality, obras, "Permiso de obra", is_active=False)
    make_procedure(make_municipality("Saira"), name="Trámite ajeno")

    assert _names(client.get(URL)) == ["Exención de tasas", "Libre deuda", "Permiso de obra"]
    assert _names(client.get(URL, params={"area_id": str(obras.id)})) == ["Permiso de obra"]
    assert _names(client.get(URL, params={"channel": "online"})) == ["Exención de tasas"]
    assert _names(client.get(URL, params={"active": "false"})) == ["Permiso de obra"]
    assert _names(client.get(URL, params={"active": "true", "q": "exencion"})) == [
        "Exención de tasas"
    ]
    page = client.get(URL, params={"limit": 1, "offset": 1})
    assert (_names(page), page.json()["total"]) == (["Libre deuda"], 3)
    assert client.get(URL, params={"channel": "fax"}).status_code == 422


def test_detail_lists_requirements_by_name_with_their_source(client):
    municipality = signed_in(client, "viewer")
    source = make_source(municipality, area=make_area(municipality))
    procedure = make_procedure(municipality)
    link_requirement(procedure, make_requirement(municipality, "Plano aprobado"), note="Visado.")
    dni = link_requirement(
        procedure, make_requirement(municipality, "DNI", source), mandatory=False, format="digital"
    )

    body = client.get(f"{URL}/{procedure.id}").json()

    assert body["requirement_count"] == 2
    assert [item["requirement"]["name"] for item in body["requirements"]] == [
        "DNI",
        "Plano aprobado",
    ]
    assert body["requirements"][0] == {
        "id": str(dni.id),
        "requirement": {
            "id": str(dni.requirement_id),
            "name": "DNI",
            "source": {
                "id": str(source.id),
                "name": "Rentas municipal",
                "level": "municipal",
                "area": {"id": str(source.area_id), "name": "Rentas"},
            },
        },
        "mandatory": False,
        "format": "digital",
        "note": "",
    }


def test_editor_adds_changes_and_removes_a_requirement(client):
    municipality = signed_in(client)
    procedure = make_procedure(municipality)
    requirement = make_requirement(municipality)
    links = f"{URL}/{procedure.id}/requirements"

    added = client.post(links, json={"requirement_id": str(requirement.id)})

    assert added.status_code == 201
    assert (added.json()["mandatory"], added.json()["format"], added.json()["note"]) == (
        True,
        "paper",
        "",
    )
    link_id = added.json()["id"]
    changed = client.patch(
        f"{links}/{link_id}", json={"mandatory": False, "format": "digital", "note": "Copia."}
    )
    assert changed.status_code == 200
    assert (changed.json()["mandatory"], changed.json()["format"], changed.json()["note"]) == (
        False,
        "digital",
        "Copia.",
    )
    assert client.patch(f"{links}/{link_id}", json={"format": "stone"}).status_code == 422
    assert client.delete(f"{links}/{link_id}").status_code == 204
    assert client.get(f"{URL}/{procedure.id}").json()["requirements"] == []


def test_a_requirement_is_asked_only_once_per_procedure(client):
    municipality = signed_in(client)
    procedure = make_procedure(municipality)
    requirement = make_requirement(municipality)
    link_requirement(procedure, requirement)

    again = client.post(
        f"{URL}/{procedure.id}/requirements", json={"requirement_id": str(requirement.id)}
    )

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "conflict"


def test_a_link_is_only_reachable_through_its_own_procedure(client):
    municipality = signed_in(client)
    procedure, other = make_procedure(municipality), make_procedure(municipality, name="Otro")
    link = link_requirement(procedure, make_requirement(municipality))
    wrong = f"{URL}/{other.id}/requirements/{link.id}"

    assert client.patch(wrong, json={"mandatory": False}).status_code == 404
    assert client.delete(wrong).status_code == 404
    assert client.get(f"{URL}/{procedure.id}").json()["requirements"][0]["mandatory"] is True


def test_references_to_another_municipality_are_rejected(client):
    municipality = signed_in(client)
    other = make_municipality("Saira")
    foreign_area, foreign_requirement = make_area(other), make_requirement(other)
    foreign_procedure = make_procedure(other, name="Ajeno")
    procedure = make_procedure(municipality)

    responses = [
        client.post(URL, json={"name": "x", "area_id": str(foreign_area.id)}),
        client.patch(f"{URL}/{procedure.id}", json={"area_id": str(foreign_area.id)}),
        client.post(
            f"{URL}/{procedure.id}/requirements",
            json={"requirement_id": str(foreign_requirement.id)},
        ),
    ]

    for response in responses:
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "invalid_reference"
    assert client.get(f"{URL}/{foreign_procedure.id}").status_code == 404
    assert (
        client.post(
            f"{URL}/{foreign_procedure.id}/requirements",
            json={"requirement_id": str(make_requirement(municipality).id)},
        ).status_code
        == 404
    )
