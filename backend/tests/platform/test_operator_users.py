import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from gobernar360.main import create_app
from gobernar360.platform.models import AuditLog
from tests.factories import (
    DEFAULT_PASSWORD,
    accept_invitation,
    admin_session,
    login,
    make_membership,
    make_municipality,
    make_user,
)

OPERATOR_EMAIL = "operator@gobernar360.test"


@pytest.fixture
def operator_client(client, demo_dashboard):
    make_user(OPERATOR_EMAIL, operator=True)
    login(client, OPERATOR_EMAIL)
    return client


@pytest.fixture
def noetinger(demo_dashboard):
    """A municipality with the demo dashboard, an administrator and an editor."""
    municipality = make_municipality("Noetinger")
    make_membership(make_user("admin@noetinger.test"), municipality, admin=True, enable=["demo"])
    make_membership(make_user("carla@noetinger.test"), municipality, grants={"demo": "editor"})
    return municipality


def _users_url(municipality) -> str:
    return f"/api/platform/municipalities/{municipality.id}/users"


def _member(client, municipality, email: str) -> dict:
    members = client.get(_users_url(municipality)).json()["items"]
    return next(member for member in members if member["user"]["email"] == email)


def _new_user(**overrides):
    return {
        "email": "nuevo@noetinger.test",
        "full_name": "Nuevo Usuario",
        "is_admin": False,
        "grants": {"demo": "viewer"},
    } | overrides


def _other_client() -> TestClient:
    return TestClient(create_app(), headers={"X-Requested-With": "gobernar360"})


def test_operator_lists_only_the_users_of_that_municipality(operator_client, noetinger):
    saira = make_municipality("Saira")
    make_membership(make_user("sara@saira.test"), saira, admin=True, enable=["demo"])

    response = operator_client.get(_users_url(noetinger))

    assert response.status_code == 200
    assert sorted(member["user"]["email"] for member in response.json()["items"]) == [
        "admin@noetinger.test",
        "carla@noetinger.test",
    ]


def test_operator_adds_a_user_with_grants_who_can_then_sign_in(operator_client, noetinger):
    response = operator_client.post(_users_url(noetinger), json=_new_user())

    assert response.status_code == 201
    assert response.json()["grants"] == {"demo": "viewer"}
    with _other_client() as other:
        accept_invitation(other, "nuevo@noetinger.test", "long-password-1")
        me = login(other, "nuevo@noetinger.test", "long-password-1").json()
    assert me["active_municipality_id"] == str(noetinger.id)
    assert me["dashboards"] == [{"key": "demo", "level": "viewer"}]


def test_operator_adds_the_first_administrator_of_a_new_municipality(operator_client):
    created = operator_client.post(
        "/api/platform/municipalities",
        json={"name": "Saira", "slug": "saira", "kind": "commune"},
    ).json()
    url = f"/api/platform/municipalities/{created['id']}/users"

    response = operator_client.post(url, json=_new_user(is_admin=True, grants={}))

    assert response.status_code == 201
    assert response.json()["is_admin"] is True
    with _other_client() as other:
        accept_invitation(other, "nuevo@noetinger.test", "long-password-1")
        me = login(other, "nuevo@noetinger.test", "long-password-1").json()
    assert me["memberships"][0]["is_admin"] is True


def test_operator_may_add_a_non_admin_as_first_user(operator_client, demo_dashboard):
    saira = make_municipality("Saira")

    response = operator_client.post(_users_url(saira), json=_new_user(grants={}))

    assert response.status_code == 201


def test_operator_changes_grants_and_admin_role(operator_client, noetinger):
    carla = _member(operator_client, noetinger, "carla@noetinger.test")
    url = f"{_users_url(noetinger)}/{carla['membership_id']}"

    changed = operator_client.patch(url, json={"grants": {"demo": "admin"}})
    promoted = operator_client.patch(url, json={"is_admin": True})

    assert changed.json()["grants"] == {"demo": "admin"}
    assert promoted.json()["is_admin"] is True


def test_operator_cannot_leave_a_municipality_without_administrator(operator_client, noetinger):
    admin = _member(operator_client, noetinger, "admin@noetinger.test")
    url = f"{_users_url(noetinger)}/{admin['membership_id']}"

    demoted = operator_client.patch(url, json={"is_admin": False})
    removed = operator_client.delete(url)

    assert (demoted.status_code, removed.status_code) == (409, 409)
    assert _member(operator_client, noetinger, "admin@noetinger.test")["is_admin"] is True


def test_operator_removes_a_user(operator_client, noetinger):
    carla = _member(operator_client, noetinger, "carla@noetinger.test")

    response = operator_client.delete(f"{_users_url(noetinger)}/{carla['membership_id']}")

    assert response.status_code == 204
    emails = [
        m["user"]["email"] for m in operator_client.get(_users_url(noetinger)).json()["items"]
    ]
    assert emails == ["admin@noetinger.test"]


def test_operator_grant_for_a_dashboard_not_enabled_is_rejected(operator_client, noetinger):
    response = operator_client.post(
        _users_url(noetinger), json=_new_user(grants={"projects": "viewer"})
    )

    assert response.status_code == 422


def test_membership_of_another_municipality_is_not_found(operator_client, noetinger):
    saira = make_municipality("Saira")
    make_membership(make_user("sara@saira.test"), saira, admin=True, enable=["demo"])
    carla = _member(operator_client, noetinger, "carla@noetinger.test")
    wrong_url = f"{_users_url(saira)}/{carla['membership_id']}"

    patched = operator_client.patch(wrong_url, json={"is_admin": True})
    password = operator_client.put(f"{wrong_url}/password", json={"password": "long-password-2"})
    deleted = operator_client.delete(wrong_url)

    assert (patched.status_code, password.status_code, deleted.status_code) == (404, 404, 404)
    unchanged = _member(operator_client, noetinger, "carla@noetinger.test")
    assert unchanged == carla
    with _other_client() as other:
        login(other, "carla@noetinger.test")


def test_unknown_municipality_returns_not_found(operator_client):
    missing = "/api/platform/municipalities/00000000-0000-0000-0000-000000000000"

    assert operator_client.get(f"{missing}/users").status_code == 404
    assert operator_client.post(f"{missing}/users", json=_new_user(grants={})).status_code == 404


def test_operator_changes_are_audited_in_the_municipality(operator_client, noetinger):
    operator_client.post(_users_url(noetinger), json=_new_user())

    with admin_session() as session:
        entry = session.scalars(select(AuditLog).where(AuditLog.action == "create")).one()
    assert entry.municipality_id == noetinger.id
    assert entry.entity_type == "memberships"
    assert entry.changes["email"] == "nuevo@noetinger.test"
    me = operator_client.get("/api/auth/me").json()
    assert str(entry.user_id) == me["user"]["id"]


def test_operator_sets_a_password_and_ends_open_sessions(operator_client, noetinger):
    carla = _member(operator_client, noetinger, "carla@noetinger.test")
    with _other_client() as carla_client:
        login(carla_client, "carla@noetinger.test")

        response = operator_client.put(
            f"{_users_url(noetinger)}/{carla['membership_id']}/password",
            json={"password": "long-password-2"},
        )

        assert response.status_code == 204
        assert carla_client.get("/api/auth/me").status_code == 401
        old = carla_client.post(
            "/api/auth/login",
            json={"email": "carla@noetinger.test", "password": DEFAULT_PASSWORD},
        )
        assert old.status_code == 401
        login(carla_client, "carla@noetinger.test", "long-password-2")


def test_short_password_is_rejected(operator_client, noetinger):
    carla = _member(operator_client, noetinger, "carla@noetinger.test")

    response = operator_client.put(
        f"{_users_url(noetinger)}/{carla['membership_id']}/password", json={"password": "short"}
    )

    assert response.status_code == 422
    with _other_client() as other:
        login(other, "carla@noetinger.test")


def test_municipality_admin_cannot_use_operator_user_routes(client, noetinger):
    login(client, "admin@noetinger.test")
    carla_id = client.get("/api/admin/users").json()["items"][1]["membership_id"]
    url = _users_url(noetinger)

    listed = client.get(url)
    added = client.post(url, json=_new_user())
    password = client.put(f"{url}/{carla_id}/password", json={"password": "long-password-2"})
    renamed = client.patch(f"/api/platform/municipalities/{noetinger.id}", json={"name": "X"})

    assert [r.status_code for r in (listed, added, password, renamed)] == [403, 403, 403, 403]


def test_municipality_admin_has_no_password_route(client, noetinger):
    login(client, "admin@noetinger.test")
    carla_id = client.get("/api/admin/users").json()["items"][1]["membership_id"]

    response = client.put(
        f"/api/admin/users/{carla_id}/password", json={"password": "long-password-2"}
    )

    assert response.status_code in (404, 405)
    with _other_client() as other:
        login(other, "carla@noetinger.test")


def test_operator_lists_enabled_dashboards_of_a_municipality(operator_client, noetinger):
    response = operator_client.get(f"/api/platform/municipalities/{noetinger.id}/dashboards")

    assert response.json() == ["demo"]


def test_operator_managing_users_still_cannot_read_municipality_data(operator_client, noetinger):
    operator_client.get(_users_url(noetinger))

    assert operator_client.get("/api/overview").status_code == 403
