import pytest

from tests.factories import login, make_municipality, make_user


@pytest.fixture
def operator_client(client, demo_dashboard):
    make_user("operator@gobernar360.test", operator=True)
    login(client, "operator@gobernar360.test")
    return client


def _create(client, **overrides):
    payload = {"name": "Noetinger", "slug": "noetinger", "kind": "municipality"} | overrides
    return client.post("/api/platform/municipalities", json=payload)


def test_operator_creates_municipality(operator_client):
    response = _create(operator_client)

    assert response.status_code == 201
    assert response.json()["slug"] == "noetinger"
    listed = operator_client.get("/api/platform/municipalities").json()
    assert [m["name"] for m in listed] == ["Noetinger"]
    assert listed[0]["dashboards"] == []


def test_duplicate_slug_returns_conflict(operator_client):
    _create(operator_client)

    response = _create(operator_client, name="Otra")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_slug_with_invalid_characters_is_rejected(operator_client):
    assert _create(operator_client, slug="Noetinger Centro").status_code == 422


def test_unknown_municipality_kind_is_rejected(operator_client):
    assert _create(operator_client, kind="province").status_code == 422


def test_non_operator_cannot_manage_municipalities(client):
    make_user("ana@noetinger.test")
    login(client, "ana@noetinger.test")

    assert client.get("/api/platform/municipalities").status_code == 403
    assert _create(client).status_code == 403


def test_operator_lists_registered_dashboards(operator_client):
    assert "demo" in operator_client.get("/api/platform/dashboards").json()


def test_operator_enables_dashboards_for_a_municipality(operator_client):
    municipality_id = _create(operator_client).json()["id"]

    response = operator_client.put(
        f"/api/platform/municipalities/{municipality_id}/dashboards", json={"keys": ["demo"]}
    )

    assert response.status_code == 200
    assert response.json()["dashboards"] == ["demo"]
    assert operator_client.get("/api/platform/municipalities").json()[0]["dashboards"] == ["demo"]


def test_operator_disables_dashboards_by_sending_a_shorter_list(operator_client):
    municipality_id = _create(operator_client).json()["id"]
    url = f"/api/platform/municipalities/{municipality_id}/dashboards"
    operator_client.put(url, json={"keys": ["demo"]})

    response = operator_client.put(url, json={"keys": []})

    assert response.json()["dashboards"] == []


def test_enabling_an_unregistered_dashboard_is_rejected(operator_client):
    municipality_id = _create(operator_client).json()["id"]

    response = operator_client.put(
        f"/api/platform/municipalities/{municipality_id}/dashboards", json={"keys": ["missing"]}
    )

    assert response.status_code == 422


def test_enabling_dashboards_for_an_unknown_municipality_returns_not_found(operator_client):
    response = operator_client.put(
        "/api/platform/municipalities/00000000-0000-0000-0000-000000000000/dashboards",
        json={"keys": []},
    )

    assert response.status_code == 404


def test_operator_creates_first_admin_of_a_municipality(operator_client, client):
    municipality_id = _create(operator_client).json()["id"]

    response = operator_client.post(
        f"/api/platform/municipalities/{municipality_id}/admins",
        json={
            "email": "Admin@Noetinger.test",
            "full_name": "Ana Admin",
            "password": "long-password-1",
        },
    )

    assert response.status_code == 201
    client.post("/api/auth/logout")
    me = login(client, "admin@noetinger.test", "long-password-1").json()
    assert me["memberships"][0]["is_admin"] is True
    assert me["active_municipality_id"] == municipality_id


def test_existing_user_becomes_admin_without_changing_their_password(operator_client, client):
    make_user("ana@noetinger.test")
    municipality = make_municipality("Saira")

    response = operator_client.post(
        f"/api/platform/municipalities/{municipality.id}/admins",
        json={"email": "ana@noetinger.test", "full_name": "Ana", "password": "another-password"},
    )

    assert response.status_code == 201
    client.post("/api/auth/logout")
    login(client, "ana@noetinger.test")  # original password still works
