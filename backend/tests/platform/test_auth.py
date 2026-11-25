from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update

from gobernar360.main import create_app
from gobernar360.platform.models import Session as SessionRow
from tests.factories import admin_session, login, make_membership, make_municipality, make_user


def test_login_with_valid_credentials_sets_session_cookie(client):
    make_user("ana@noetinger.test")

    response = client.post(
        "/api/auth/login", json={"email": "ana@noetinger.test", "password": "secret-pass-1"}
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "ana@noetinger.test"
    set_cookie = response.headers["set-cookie"].lower()
    assert "g360_session=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


def test_login_with_wrong_password_returns_invalid_credentials(client):
    make_user("ana@noetinger.test")

    wrong_password = client.post(
        "/api/auth/login", json={"email": "ana@noetinger.test", "password": "not-the-password"}
    )
    unknown_email = client.post(
        "/api/auth/login", json={"email": "nobody@noetinger.test", "password": "secret-pass-1"}
    )

    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_ignores_email_case_and_surrounding_spaces(client):
    make_user("ana@muni.gob.ar")

    response = client.post(
        "/api/auth/login", json={"email": " Ana@Muni.gob.ar ", "password": "secret-pass-1"}
    )

    assert response.status_code == 200


def test_inactive_user_cannot_log_in(client):
    make_user("ana@noetinger.test", active=False)

    response = client.post(
        "/api/auth/login", json={"email": "ana@noetinger.test", "password": "secret-pass-1"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_me_without_session_returns_not_authenticated(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_returns_the_signed_in_user(client):
    make_user("ana@noetinger.test")
    login(client, "ana@noetinger.test")

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "ana@noetinger.test"
    assert response.json()["user"]["is_platform_operator"] is False


def test_expired_session_is_rejected(client):
    make_user("ana@noetinger.test")
    login(client, "ana@noetinger.test")
    with admin_session() as session, session.begin():
        session.execute(
            update(SessionRow).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_logout_invalidates_the_session(client):
    make_user("ana@noetinger.test")
    token = login(client, "ana@noetinger.test").cookies["g360_session"]

    assert client.post("/api/auth/logout").status_code == 204

    # Replaying the old cookie must not work either.
    client.cookies.set("g360_session", token)
    assert client.get("/api/auth/me").status_code == 401


def test_single_membership_becomes_active_municipality_on_login(client):
    user = make_user("ana@noetinger.test")
    municipality = make_municipality("Noetinger")
    make_membership(user, municipality)

    body = login(client, "ana@noetinger.test").json()

    assert body["active_municipality_id"] == str(municipality.id)
    assert [m["municipality"]["name"] for m in body["memberships"]] == ["Noetinger"]


def test_user_with_several_memberships_chooses_the_active_municipality(client):
    user = make_user("ana@noetinger.test")
    first = make_municipality("Noetinger")
    second = make_municipality("Saira")
    make_membership(user, first)
    make_membership(user, second)

    assert login(client, "ana@noetinger.test").json()["active_municipality_id"] is None
    response = client.post(
        "/api/auth/active-municipality", json={"municipality_id": str(second.id)}
    )

    assert response.status_code == 200
    assert response.json()["active_municipality_id"] == str(second.id)
    assert client.get("/api/auth/me").json()["active_municipality_id"] == str(second.id)


def test_user_cannot_activate_a_municipality_they_do_not_belong_to(client):
    make_user("ana@noetinger.test")
    other = make_municipality("Saira")
    login(client, "ana@noetinger.test")

    response = client.post("/api/auth/active-municipality", json={"municipality_id": str(other.id)})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_unsafe_request_without_csrf_header_is_rejected():
    make_user("ana@noetinger.test")
    with TestClient(create_app()) as bare_client:
        response = bare_client.post(
            "/api/auth/login", json={"email": "ana@noetinger.test", "password": "secret-pass-1"}
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_header_missing"


def test_signing_out_removes_the_cookie_from_the_whole_site(client):
    make_membership(make_user("ana@noetinger.test"), make_municipality("Noetinger"))
    login(client, "ana@noetinger.test")

    response = client.post("/api/auth/logout")

    cookie = response.headers["set-cookie"]
    assert cookie.startswith("g360_session=") and "Max-Age=0" in cookie
    assert "Path=/;" in f"{cookie};"


def test_switching_to_a_municipality_that_is_not_one_s_own_is_refused(client):
    make_membership(make_user("ana@noetinger.test"), make_municipality("Noetinger"))
    other = make_municipality("Saira")
    login(client, "ana@noetinger.test")

    response = client.post("/api/auth/active-municipality", json={"municipality_id": str(other.id)})

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "forbidden",
        "message": "You do not belong to this municipality.",
    }


def test_changing_the_password_asks_for_the_current_one(client):
    make_membership(make_user("ana@noetinger.test"), make_municipality("Noetinger"))
    login(client, "ana@noetinger.test")

    response = client.post(
        "/api/auth/password",
        json={"current_password": "not-this-one", "new_password": "another-pass-2"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "invalid_credentials",
        "message": "The current password is incorrect.",
    }
