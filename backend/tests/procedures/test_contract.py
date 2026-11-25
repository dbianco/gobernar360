from tests.contract import administrator, check_reference, check_trace, write
from tests.procedures.factories import (
    BASE,
    link_requirement,
    make_area,
    make_procedure,
    make_requirement,
    make_source,
)


def test_what_is_created_leaves_a_trace_of_what_it_was(client):
    municipality = administrator(client, "procedures")
    area, requirement = make_area(municipality), make_requirement(municipality)
    procedure = make_procedure(municipality, area)

    for path, body in (
        ("areas", {"name": "Obras"}),
        ("sources", {"name": "RENAPER", "level": "national"}),
        ("requirements", {"name": "DNI", "description": "x"}),
        ("procedures", {"name": "Poda", "area_id": str(area.id)}),
        (
            f"procedures/{procedure.id}/requirements",
            {"requirement_id": str(requirement.id), "mandatory": False},
        ),
    ):
        more = {"procedure_id": str(procedure.id)} if path.endswith("/requirements") else {}
        check_trace(client, "POST", f"{BASE}/{path}", body, "create", **more)


def test_ids_that_are_not_the_municipality_s_are_refused_by_name(client):
    municipality = administrator(client, "procedures")
    requirement, procedure = make_requirement(municipality), make_procedure(municipality)

    for method, path, body, field in (
        ("POST", "requirements", {"name": "DNI"}, "source_id"),
        ("PATCH", f"requirements/{requirement.id}", {}, "source_id"),
        ("POST", "procedures", {"name": "Poda"}, "area_id"),
        ("PATCH", f"procedures/{procedure.id}", {}, "area_id"),
        ("POST", f"procedures/{procedure.id}/requirements", {}, "requirement_id"),
        ("POST", "sources", {"name": "Rentas", "level": "municipal"}, "area_id"),
    ):
        check_reference(client, method, f"{BASE}/{path}", body, field)


def test_only_what_was_sent_of_what_a_procedure_asks_for_changes(client):
    municipality = administrator(client, "procedures")
    procedure = make_procedure(municipality)
    link = link_requirement(
        procedure, make_requirement(municipality), mandatory=False, format="digital", note="x"
    )
    url = f"{BASE}/procedures/{procedure.id}/requirements/{link.id}"

    check_trace(client, "PATCH", url, {"note": "y"}, "update")

    [asked] = client.get(f"{BASE}/procedures/{procedure.id}").json()["requirements"]
    assert (asked["mandatory"], asked["format"], asked["note"]) == (False, "digital", "y")


def test_a_procedure_asks_for_something_once_and_others_may_too(client):
    municipality = administrator(client, "procedures")
    first, second = (make_procedure(municipality, name=name) for name in ("Uno", "Dos"))
    dni, debt = (make_requirement(municipality, name) for name in ("DNI", "Deuda"))
    body = {"requirement_id": str(dni.id)}
    write(client, "POST", f"{BASE}/procedures/{first.id}/requirements", body)

    again = client.post(f"{BASE}/procedures/{first.id}/requirements", json=body)

    assert again.status_code == 409
    assert again.json()["error"] == {
        "code": "conflict",
        "message": "This procedure already asks for that requirement.",
    }
    write(client, "POST", f"{BASE}/procedures/{second.id}/requirements", body)
    write(
        client,
        "POST",
        f"{BASE}/procedures/{first.id}/requirements",
        {"requirement_id": str(debt.id)},
    )


def test_what_a_procedure_asks_for_is_listed_by_name_ignoring_case_and_accents(client):
    municipality = administrator(client, "procedures")
    procedure = make_procedure(municipality)
    for name in ("dni", "Álbum", "Boleta", "acta"):
        link_requirement(procedure, make_requirement(municipality, name))

    asked = client.get(f"{BASE}/procedures/{procedure.id}").json()["requirements"]

    assert [link["requirement"]["name"] for link in asked] == ["acta", "Álbum", "Boleta", "dni"]


def test_a_free_procedure_has_no_cost_when_created_or_changed(client):
    municipality = administrator(client, "procedures")
    body = {"name": "Poda", "area_id": str(make_area(municipality).id), "cost": "5"}
    created = client.post(f"{BASE}/procedures", json=body | {"is_free": True})
    assert created.status_code == 422
    [detail] = created.json()["error"]["details"]
    assert detail["message"].endswith("a free procedure has no cost")

    paid = write(client, "POST", f"{BASE}/procedures", body | {"is_free": False}).json()
    changed = client.patch(f"{BASE}/procedures/{paid['id']}", json={"is_free": True, "cost": "5"})
    assert changed.status_code == 422
    assert changed.json()["error"] == {
        "code": "validation_error",
        "message": "A free procedure has no cost.",
    }


def test_a_source_keeps_its_area_only_while_it_is_municipal(client):
    municipality = administrator(client, "procedures")
    first, second = (make_area(municipality, name) for name in ("Rentas", "Obras"))
    source = make_source(municipality, area=first)
    url = f"{BASE}/sources/{source.id}"

    def area(**changes):
        changed = write(client, "PATCH", url, changes).json()["area"]
        return changed and changed["name"]

    assert area(name="Rentas municipal") == "Rentas"
    assert area(area_id=str(second.id)) == "Obras"
    assert area(level="municipal") == "Obras"
    assert area(level="national") is None
    refused = client.patch(url, json={"area_id": str(first.id)})
    assert refused.status_code == 422
    assert area(level="municipal", area_id=str(first.id)) == "Rentas"
    assert area(area_id=None) is None


def test_sources_and_requirements_are_listed_by_name(client):
    municipality = administrator(client, "procedures")
    for name in ("Rentas", "ANSES", "Catastro"):
        make_source(municipality, name)
    for name in ("dni", "Álbum", "Boleta", "acta"):
        make_requirement(municipality, name)

    def names(path):
        return [item["name"] for item in client.get(f"{BASE}/{path}").json()]

    assert names("sources") == ["ANSES", "Catastro", "Rentas"]
    assert names("requirements") == ["acta", "Álbum", "Boleta", "dni"]
