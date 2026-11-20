import pytest
from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform.models import AuditLog
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


def _names(response):
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()]


def test_admin_manages_areas(client):
    signed_in(client, "admin")

    created = client.post(f"{BASE}/areas", json={"name": "  Obras Privadas "})
    assert created.status_code == 201
    assert created.json() == {"id": created.json()["id"], "name": "Obras Privadas"}
    area_id = created.json()["id"]
    client.post(f"{BASE}/areas", json={"name": "Catastro"})

    assert client.patch(f"{BASE}/areas/{area_id}", json={"name": "Obras"}).json()["name"] == "Obras"
    assert _names(client.get(f"{BASE}/areas")) == ["Catastro", "Obras"]
    assert client.delete(f"{BASE}/areas/{area_id}").status_code == 204
    assert _names(client.get(f"{BASE}/areas")) == ["Catastro"]


@pytest.mark.parametrize("level", ["viewer", "editor"])
def test_only_admins_change_areas_and_sources(client, level):
    municipality = signed_in(client, level)
    area, source = make_area(municipality), make_source(municipality)

    assert client.post(f"{BASE}/areas", json={"name": "x"}).status_code == 403
    assert client.patch(f"{BASE}/areas/{area.id}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{BASE}/areas/{area.id}").status_code == 403
    assert client.post(f"{BASE}/sources", json={"name": "x", "level": "other"}).status_code == 403
    assert client.patch(f"{BASE}/sources/{source.id}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{BASE}/sources/{source.id}").status_code == 403
    assert _names(client.get(f"{BASE}/areas")) == ["Rentas"]
    assert _names(client.get(f"{BASE}/sources")) == ["Rentas municipal"]


def test_member_without_access_reads_nothing(client):
    signed_in(client, None)

    for path in ("areas", "sources", "requirements"):
        assert client.get(f"{BASE}/{path}").status_code == 403


def test_admin_creates_a_municipal_source_with_its_area(client):
    municipality = signed_in(client, "admin")
    area = make_area(municipality)

    created = client.post(
        f"{BASE}/sources",
        json={"name": "Rentas municipal", "level": "municipal", "area_id": str(area.id)},
    )

    assert created.status_code == 201
    assert created.json() == {
        "id": created.json()["id"],
        "name": "Rentas municipal",
        "level": "municipal",
        "area": {"id": str(area.id), "name": "Rentas"},
    }


def test_only_municipal_sources_have_an_area(client):
    municipality = signed_in(client, "admin")
    area = make_area(municipality)
    municipal = make_source(municipality, area=area)

    created = client.post(
        f"{BASE}/sources", json={"name": "ARCA", "level": "national", "area_id": str(area.id)}
    )
    patched = client.patch(f"{BASE}/sources/{municipal.id}", json={"level": "provincial"})

    assert created.status_code == 422
    # Changing the level away from municipal drops the area instead of failing.
    assert patched.status_code == 200
    assert (patched.json()["level"], patched.json()["area"]) == ("provincial", None)


def test_source_level_must_be_known(client):
    signed_in(client, "admin")

    assert (
        client.post(f"{BASE}/sources", json={"name": "x", "level": "galactic"}).status_code == 422
    )
    assert client.post(f"{BASE}/sources", json={"name": "x"}).status_code == 422


def test_editor_manages_requirements(client):
    municipality = signed_in(client, "editor")
    source = make_source(municipality)

    created = client.post(
        f"{BASE}/requirements",
        json={"name": "Libre deuda", "description": "De tasas.", "source_id": str(source.id)},
    )
    assert created.status_code == 201
    assert created.json() == {
        "id": created.json()["id"],
        "name": "Libre deuda",
        "description": "De tasas.",
        "source": {
            "id": str(source.id),
            "name": "Rentas municipal",
            "level": "municipal",
            "area": None,
        },
        "procedure_count": 0,
    }
    requirement_id = created.json()["id"]

    patched = client.patch(f"{BASE}/requirements/{requirement_id}", json={"source_id": None})
    assert patched.status_code == 200
    assert patched.json()["source"] is None
    assert client.delete(f"{BASE}/requirements/{requirement_id}").status_code == 204
    assert client.get(f"{BASE}/requirements").json() == []


def test_viewer_cannot_change_requirements(client):
    municipality = signed_in(client, "viewer")
    requirement = make_requirement(municipality)

    assert client.post(f"{BASE}/requirements", json={"name": "x"}).status_code == 403
    assert (
        client.patch(f"{BASE}/requirements/{requirement.id}", json={"name": "x"}).status_code == 403
    )
    assert client.delete(f"{BASE}/requirements/{requirement.id}").status_code == 403
    assert _names(client.get(f"{BASE}/requirements")) == ["Libre deuda municipal"]


def test_requirements_are_listed_by_name_with_how_many_procedures_use_them(client):
    municipality = signed_in(client, "viewer")
    dni = make_requirement(municipality, "DNI")
    plan = make_requirement(municipality, "Plano aprobado")
    make_requirement(municipality, "Árbol genealógico")
    link_requirement(make_procedure(municipality, name="Uno"), dni)
    # Inactive procedures still use the requirement, so it cannot be deleted.
    link_requirement(make_procedure(municipality, name="Dos", is_active=False), dni)
    link_requirement(make_procedure(municipality, name="Tres"), plan)

    response = client.get(f"{BASE}/requirements")

    assert [(item["name"], item["procedure_count"]) for item in response.json()] == [
        ("Árbol genealógico", 0),
        ("DNI", 2),
        ("Plano aprobado", 1),
    ]


def test_requirements_are_searched_ignoring_case_and_accents(client):
    municipality = signed_in(client, "viewer")
    make_requirement(municipality, "Certificado de Catastro")
    make_requirement(municipality, "Árbol genealógico")

    assert _names(client.get(f"{BASE}/requirements", params={"q": "arbol"})) == [
        "Árbol genealógico"
    ]
    assert _names(client.get(f"{BASE}/requirements", params={"q": "100%"})) == []


def test_references_to_another_municipality_are_rejected(client):
    municipality = signed_in(client, "admin")
    other = make_municipality("Saira")
    foreign_area, foreign_source = make_area(other), make_source(other)
    source = make_source(municipality)
    requirement = make_requirement(municipality)

    responses = [
        client.post(
            f"{BASE}/sources",
            json={"name": "x", "level": "municipal", "area_id": str(foreign_area.id)},
        ),
        client.patch(f"{BASE}/sources/{source.id}", json={"area_id": str(foreign_area.id)}),
        client.post(
            f"{BASE}/requirements", json={"name": "x", "source_id": str(foreign_source.id)}
        ),
        client.patch(
            f"{BASE}/requirements/{requirement.id}", json={"source_id": str(foreign_source.id)}
        ),
    ]

    for response in responses:
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "invalid_reference"


def test_rows_of_another_municipality_are_invisible(client):
    other = make_municipality("Saira")
    foreign_area = make_area(other, "Ajena")
    make_source(other, "Fuente ajena")
    make_requirement(other, "Requisito ajeno")
    signed_in(client, "admin")

    for path in ("areas", "sources", "requirements"):
        assert client.get(f"{BASE}/{path}").json() == []
    assert client.patch(f"{BASE}/areas/{foreign_area.id}", json={"name": "x"}).status_code == 404
    assert client.delete(f"{BASE}/areas/{foreign_area.id}").status_code == 404


def test_catalog_rows_in_use_cannot_be_deleted(client):
    municipality = signed_in(client, "admin")
    area = make_area(municipality)
    source = make_source(municipality, area=area)
    requirement = make_requirement(municipality, source=source)
    procedure = make_procedure(municipality, make_area(municipality, "Comercio"))
    link_requirement(procedure, requirement)

    for path in (
        f"areas/{area.id}",
        f"areas/{procedure.area_id}",
        f"sources/{source.id}",
        f"requirements/{requirement.id}",
    ):
        response = client.delete(f"{BASE}/{path}")
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "in_use"


def test_names_are_required_and_bounded(client):
    signed_in(client, "admin")

    for path, extra in (("areas", {}), ("sources", {"level": "other"}), ("requirements", {})):
        assert client.post(f"{BASE}/{path}", json={"name": "  "} | extra).status_code == 422
        assert client.post(f"{BASE}/{path}", json={"name": "x" * 201} | extra).status_code == 422


def test_creating_a_requirement_is_audited(client):
    municipality = signed_in(client, "editor")

    created = client.post(f"{BASE}/requirements", json={"name": "DNI"})

    with tenant_session(municipality.id) as db:
        entry = db.scalars(select(AuditLog)).one()
    assert (entry.action, entry.entity_type, entry.entity_id) == (
        "create",
        "procedures_requirements",
        created.json()["id"],
    )
