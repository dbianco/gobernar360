from sqlalchemy import select, text

from gobernar360.core.db import get_admin_engine, tenant_session
from gobernar360.platform.models import AuditLog
from tests.environment.factories import (
    BASE,
    environment_member,
    make_subcategory,
    make_value,
    make_variable,
)
from tests.factories import login, make_municipality


def _admin(client):
    municipality = environment_member("admin")
    login(client, "ana@noetinger.test")
    return municipality


def _variable_payload(subcategory_id, **overrides):
    return {
        "subcategory_id": str(subcategory_id),
        "name": "Consumo del palacio municipal",
        "unit": "kWh",
        "frequency": "monthly",
        "target": "12000.5",
        "direction": "lower_is_better",
        "source": "external",
        "annual_aggregation": "sum",
    } | overrides


def test_dashboard_admin_creates_subcategory_and_variable(client):
    _admin(client)

    subcategory = client.post(
        f"{BASE}/subcategories", json={"category": "energy", "name": "  Consumo eléctrico  "}
    )
    variable = client.post(f"{BASE}/variables", json=_variable_payload(subcategory.json()["id"]))

    assert (subcategory.status_code, variable.status_code) == (201, 201)
    assert subcategory.json()["name"] == "Consumo eléctrico"
    assert variable.json() | {"id": None} == {
        "id": None,
        "name": "Consumo del palacio municipal",
        "unit": "kWh",
        "frequency": "monthly",
        "target": 12000.5,
        "direction": "lower_is_better",
        "source": "external",
        "annual_aggregation": "sum",
        "subcategory": subcategory.json(),
    }
    assert client.get(f"{BASE}/subcategories", params={"category": "energy"}).json() == [
        subcategory.json()
    ]
    assert client.get(f"{BASE}/subcategories", params={"category": "water"}).json() == []
    assert client.get(f"{BASE}/variables", params={"category": "energy"}).json() == [
        variable.json()
    ]
    assert client.get(f"{BASE}/variables", params={"category": "water"}).json() == []


def test_variable_defaults_apply_when_optional_fields_are_omitted(client):
    municipality = _admin(client)
    subcategory = make_subcategory(municipality)

    response = client.post(
        f"{BASE}/variables",
        json={"subcategory_id": str(subcategory.id), "name": "Arbolado", "frequency": "annual"},
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["unit"], body["target"], body["direction"], body["source"]) == (
        "",
        None,
        "higher_is_better",
        "municipal",
    )


def test_unknown_category_is_rejected(client):
    _admin(client)

    response = client.post(f"{BASE}/subcategories", json={"category": "noise", "name": "Ruido"})

    assert response.status_code == 422
    assert client.get(f"{BASE}/subcategories", params={"category": "noise"}).status_code == 422


def test_dashboard_admin_updates_a_variable_and_clears_its_target(client):
    municipality = _admin(client)
    variable = make_variable(municipality, target=100)
    other = make_subcategory(municipality, "water", "Calidad")

    response = client.patch(
        f"{BASE}/variables/{variable.id}",
        json={"name": "Consumo total", "target": None, "subcategory_id": str(other.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["target"], body["unit"]) == ("Consumo total", None, "kWh")
    assert body["subcategory"]["category"] == "water"


def test_variable_frequency_cannot_be_changed(client):
    municipality = _admin(client)
    variable = make_variable(municipality)

    response = client.patch(f"{BASE}/variables/{variable.id}", json={"frequency": "annual"})

    assert response.status_code == 422


def test_required_variable_fields_cannot_be_cleared(client):
    municipality = _admin(client)
    variable = make_variable(municipality)

    assert client.patch(f"{BASE}/variables/{variable.id}", json={"name": None}).status_code == 422


def test_editor_cannot_change_parameters(client):
    municipality = environment_member("editor")
    subcategory = make_subcategory(municipality)
    variable = make_variable(municipality, subcategory)
    login(client, "ana@noetinger.test")

    assert (
        client.post(f"{BASE}/subcategories", json={"category": "air", "name": "x"}).status_code
        == 403
    )
    assert (
        client.post(f"{BASE}/variables", json=_variable_payload(subcategory.id)).status_code == 403
    )
    assert client.patch(f"{BASE}/variables/{variable.id}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{BASE}/subcategories/{subcategory.id}").status_code == 403


def test_viewer_lists_parameters(client):
    municipality = environment_member("viewer")
    make_variable(municipality)
    login(client, "ana@noetinger.test")

    assert [s["name"] for s in client.get(f"{BASE}/subcategories").json()] == ["Consumo eléctrico"]
    assert [v["name"] for v in client.get(f"{BASE}/variables").json()] == [
        "Consumo del palacio municipal"
    ]


def test_member_without_grant_cannot_list_parameters(client):
    environment_member(None)
    login(client, "ana@noetinger.test")

    assert client.get(f"{BASE}/subcategories").status_code == 403
    assert client.get(f"{BASE}/variables").status_code == 403


def test_parameters_of_another_municipality_are_not_listed_nor_editable(client):
    other = make_municipality("Saira")
    foreign = make_variable(other)
    _admin(client)

    assert client.get(f"{BASE}/subcategories").json() == []
    assert client.get(f"{BASE}/variables").json() == []
    assert client.patch(f"{BASE}/variables/{foreign.id}", json={"name": "x"}).status_code == 404
    assert client.delete(f"{BASE}/variables/{foreign.id}").status_code == 404
    assert client.delete(f"{BASE}/subcategories/{foreign.subcategory_id}").status_code == 404


def test_variable_cannot_reference_subcategory_of_another_municipality(client):
    other = make_municipality("Saira")
    foreign = make_subcategory(other)
    municipality = _admin(client)
    variable = make_variable(municipality)

    created = client.post(f"{BASE}/variables", json=_variable_payload(foreign.id))
    moved = client.patch(
        f"{BASE}/variables/{variable.id}", json={"subcategory_id": str(foreign.id)}
    )

    assert (created.status_code, moved.status_code) == (422, 422)
    assert created.json()["error"]["code"] == "invalid_reference"


def test_deleting_parameters_in_use_returns_in_use(client):
    municipality = _admin(client)
    subcategory = make_subcategory(municipality)
    variable = make_variable(municipality, subcategory)
    make_value(municipality, variable, 2026, 1, 10)

    for path in (f"subcategories/{subcategory.id}", f"variables/{variable.id}"):
        response = client.delete(f"{BASE}/{path}")
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "in_use"
    assert len(client.get(f"{BASE}/variables").json()) == 1


def test_unused_parameters_can_be_deleted(client):
    municipality = _admin(client)
    subcategory = make_subcategory(municipality)
    variable = make_variable(municipality, subcategory)

    assert client.delete(f"{BASE}/variables/{variable.id}").status_code == 204
    assert client.delete(f"{BASE}/subcategories/{subcategory.id}").status_code == 204
    assert client.get(f"{BASE}/subcategories").json() == []


def test_parameter_change_is_audited(client):
    municipality = _admin(client)

    subcategory_id = client.post(
        f"{BASE}/subcategories", json={"category": "waste", "name": "Reciclado"}
    ).json()["id"]
    client.patch(f"{BASE}/subcategories/{subcategory_id}", json={"name": "Reciclaje"})
    client.delete(f"{BASE}/subcategories/{subcategory_id}")

    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert [(e.action, e.entity_type) for e in entries] == [
        ("create", "environment_subcategories"),
        ("update", "environment_subcategories"),
        ("delete", "environment_subcategories"),
    ]
    assert entries[1].changes == {"name": "Reciclaje"}


def test_every_environment_table_enforces_tenant_isolation():
    with get_admin_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                "EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid "
                "AND p.polname = 'tenant_isolation') "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' "
                "AND c.relname LIKE 'environment\\_%'"
            )
        ).all()

    assert sorted(row[0] for row in rows) == [
        "environment_subcategories",
        "environment_values",
        "environment_variables",
    ]
    assert all(row[1] and row[2] and row[3] for row in rows)


def test_variables_are_listed_by_subcategory_then_name_and_filtered(client):
    municipality = environment_member("viewer")
    lighting = make_subcategory(municipality, "energy", "Alumbrado")
    buildings = make_subcategory(municipality, "energy", "Edificios")
    water = make_subcategory(municipality, "water", "Agua potable")
    make_variable(municipality, buildings, "Consumo del palacio")
    make_variable(municipality, lighting, "Luminarias LED")
    make_variable(municipality, lighting, "Consumo del alumbrado")
    make_variable(municipality, water, "Cloro residual")
    login(client, "ana@noetinger.test")

    def names(**params) -> list[str]:
        return [v["name"] for v in client.get(f"{BASE}/variables", params=params).json()]

    assert names() == [
        "Cloro residual",
        "Consumo del alumbrado",
        "Luminarias LED",
        "Consumo del palacio",
    ]
    assert names(category="energy") == [
        "Consumo del alumbrado",
        "Luminarias LED",
        "Consumo del palacio",
    ]
    assert names(subcategory_id=str(lighting.id)) == ["Consumo del alumbrado", "Luminarias LED"]
