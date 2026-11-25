import pytest
from sqlalchemy import select

from gobernar360.platform.models import AuditLog
from tests.factories import admin_session, login, make_user


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
    assert response.json()["error"] == {"code": "not_found", "message": "Municipality not found."}


def _patch(client, municipality_id, **changes):
    return client.patch(f"/api/platform/municipalities/{municipality_id}", json=changes)


def test_operator_renames_a_municipality_and_changes_its_kind(operator_client):
    municipality_id = _create(operator_client).json()["id"]
    operator_client.put(
        f"/api/platform/municipalities/{municipality_id}/dashboards", json={"keys": ["demo"]}
    )

    renamed = _patch(operator_client, municipality_id, name="  Noetinger Nuevo  ")
    changed = _patch(operator_client, municipality_id, kind="commune")

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Noetinger Nuevo"
    assert changed.json() == {
        "id": municipality_id,
        "name": "Noetinger Nuevo",
        "slug": "noetinger",
        "kind": "commune",
        "dashboards": ["demo"],
    }


def test_municipality_slug_and_unknown_fields_cannot_be_patched(operator_client):
    municipality_id = _create(operator_client).json()["id"]

    slug = _patch(operator_client, municipality_id, name="Otro", slug="otro")
    unknown = _patch(operator_client, municipality_id, name="Otro", color="red")
    bad_kind = _patch(operator_client, municipality_id, kind="province")

    assert (slug.status_code, unknown.status_code, bad_kind.status_code) == (422, 422, 422)
    listed = operator_client.get("/api/platform/municipalities").json()[0]
    assert (listed["name"], listed["slug"], listed["kind"]) == (
        "Noetinger",
        "noetinger",
        "municipality",
    )


def test_blank_municipality_name_is_rejected(operator_client):
    municipality_id = _create(operator_client).json()["id"]

    assert _patch(operator_client, municipality_id, name="   ").status_code == 422
    assert _patch(operator_client, municipality_id, name=None).status_code == 422


def test_patching_an_unknown_municipality_returns_not_found(operator_client):
    response = _patch(operator_client, "00000000-0000-0000-0000-000000000000", name="Otro")

    assert response.status_code == 404


def test_non_operator_cannot_patch_a_municipality(operator_client, client):
    municipality_id = _create(operator_client).json()["id"]
    client.post("/api/auth/logout")
    make_user("ana@noetinger.test")
    login(client, "ana@noetinger.test")

    assert _patch(client, municipality_id, name="Otro").status_code == 403


def test_municipalities_are_listed_by_name(operator_client):
    for name in ("Saira", "Noetinger", "Tortugas", "Alicia"):
        _create(operator_client, name=name, slug=name.lower())

    listed = operator_client.get("/api/platform/municipalities").json()

    assert [m["name"] for m in listed] == ["Alicia", "Noetinger", "Saira", "Tortugas"]


def test_a_slug_in_use_says_so(operator_client):
    _create(operator_client)

    assert _create(operator_client, name="Otra").json()["error"] == {
        "code": "conflict",
        "message": "A municipality with this slug already exists.",
    }


def test_every_dashboard_that_does_not_exist_is_named(operator_client):
    municipality_id = _create(operator_client).json()["id"]

    response = operator_client.put(
        f"/api/platform/municipalities/{municipality_id}/dashboards",
        json={"keys": ["lottery", "demo", "casino"]},
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "validation_error",
        "message": "Unknown dashboards: casino, lottery.",
    }


def test_a_password_set_by_the_operator_leaves_a_trace_without_the_password(operator_client):
    municipality_id = _create(operator_client).json()["id"]
    url = f"/api/platform/municipalities/{municipality_id}/users"
    member = operator_client.post(
        url, json={"email": "ana@noetinger.test", "full_name": "Ana"}
    ).json()
    path = f"{url}/{member['membership_id']}/password"

    response = operator_client.put(path, json={"password": "a-long-password-1"})

    assert response.status_code in (200, 204), response.text
    with admin_session() as session:
        entries = session.scalars(
            select(AuditLog).where(AuditLog.action == "update").order_by(AuditLog.created_at)
        ).all()
    assert [entry.changes for entry in entries] == [{"password": "changed"}]
