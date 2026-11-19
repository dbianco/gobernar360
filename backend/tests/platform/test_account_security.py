"""Regression tests for findings of the final review."""

from sqlalchemy import select

from gobernar360.platform.models import AuditLog
from tests.factories import admin_session, login, make_membership, make_municipality, make_user

NEW_PASSWORD = "a-brand-new-password"


def _operator(client):
    make_user("operator@gobernar360.test", operator=True)
    login(client, "operator@gobernar360.test")


def test_operator_created_admin_gets_the_operator_password_even_if_the_email_was_preregistered(
    client,
):
    # Someone (e.g. the admin of another municipality) registered the email first.
    make_user("intendente@beta.test", password="chosen-by-someone-else")
    beta = make_municipality("Beta")
    _operator(client)

    response = client.post(
        f"/api/platform/municipalities/{beta.id}/users",
        json={
            "email": "intendente@beta.test",
            "full_name": "Intendente",
            "password": NEW_PASSWORD,
            "is_admin": True,
            "existing_account": "replace_password",
        },
    )
    client.post("/api/auth/logout")

    assert response.status_code == 201
    old = client.post(
        "/api/auth/login",
        json={"email": "intendente@beta.test", "password": "chosen-by-someone-else"},
    )
    assert old.status_code == 401
    assert login(client, "intendente@beta.test", NEW_PASSWORD).json()["memberships"][0]["is_admin"]


def test_operator_created_admin_invalidates_sessions_of_the_preexisting_account(client):
    make_user("intendente@beta.test")
    beta = make_municipality("Beta")
    stale_cookie = login(client, "intendente@beta.test").cookies["g360_session"]
    client.post("/api/auth/logout")
    stale_cookie = login(client, "intendente@beta.test").cookies["g360_session"]
    client.cookies.clear()
    _operator(client)

    client.post(
        f"/api/platform/municipalities/{beta.id}/users",
        json={
            "email": "intendente@beta.test",
            "full_name": "Intendente",
            "password": NEW_PASSWORD,
            "is_admin": True,
            "existing_account": "replace_password",
        },
    )

    client.cookies.clear()
    client.cookies.set("g360_session", stale_cookie)
    assert client.get("/api/auth/me").status_code == 401


def _add_to(client, municipality, **fields):
    return client.post(
        f"/api/platform/municipalities/{municipality.id}/users",
        json={"email": "intendente@beta.test", "full_name": "X", "password": NEW_PASSWORD} | fields,
    )


def test_operator_must_choose_what_happens_to_an_existing_account(client):
    make_user("intendente@beta.test", password="chosen-by-its-owner")
    beta = make_municipality("Beta")
    _operator(client)

    response = _add_to(client, beta)
    client.post("/api/auth/logout")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_exists"
    me = login(client, "intendente@beta.test", "chosen-by-its-owner").json()
    assert me["memberships"] == []


def test_operator_adds_an_existing_account_keeping_its_password_and_sessions(client):
    make_user("intendente@beta.test", password="chosen-by-its-owner")
    beta = make_municipality("Beta")
    session_cookie = login(client, "intendente@beta.test", "chosen-by-its-owner").cookies[
        "g360_session"
    ]
    client.cookies.clear()
    _operator(client)

    response = _add_to(client, beta, existing_account="keep_password")

    assert response.status_code == 201
    client.cookies.clear()
    client.cookies.set("g360_session", session_cookie)
    assert client.get("/api/auth/me").json()["memberships"][0]["municipality"]["name"] == "Beta"


def test_operator_adds_themselves_to_a_municipality_and_stays_signed_in(client):
    beta = make_municipality("Beta")
    _operator(client)

    response = client.post(
        f"/api/platform/municipalities/{beta.id}/users",
        json={
            "email": "operator@gobernar360.test",
            "full_name": "Operator",
            "password": NEW_PASSWORD,
            "is_admin": True,
            "existing_account": "keep_password",
        },
    )

    assert response.status_code == 201
    assert client.get("/api/auth/me").json()["memberships"][0]["is_admin"] is True


def test_replacing_the_password_of_an_existing_account_is_audited(client):
    make_user("intendente@beta.test")
    beta = make_municipality("Beta")
    _operator(client)

    _add_to(client, beta, existing_account="replace_password")
    _add_to(client, make_municipality("Gama"), existing_account="keep_password")

    with admin_session() as session:
        entries = session.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert [entry.changes.get("password") for entry in entries] == ["replaced", None]


def test_operator_adding_someone_who_is_already_a_member_changes_nothing(client):
    beta = make_municipality("Beta")
    make_membership(make_user("intendente@beta.test"), beta, admin=True)
    _operator(client)

    response = client.post(
        f"/api/platform/municipalities/{beta.id}/users",
        json={
            "email": "intendente@beta.test",
            "full_name": "X",
            "password": NEW_PASSWORD,
            "existing_account": "replace_password",
        },
    )
    client.post("/api/auth/logout")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    login(client, "intendente@beta.test")


def test_user_changes_their_own_password(client):
    make_user("ana@noetinger.test")
    login(client, "ana@noetinger.test")

    response = client.post(
        "/api/auth/password",
        json={"current_password": "secret-pass-1", "new_password": NEW_PASSWORD},
    )
    client.post("/api/auth/logout")

    assert response.status_code == 204
    old = client.post(
        "/api/auth/login", json={"email": "ana@noetinger.test", "password": "secret-pass-1"}
    )
    assert old.status_code == 401
    login(client, "ana@noetinger.test", NEW_PASSWORD)


def test_password_change_requires_the_current_password(client):
    make_user("ana@noetinger.test")
    login(client, "ana@noetinger.test")

    response = client.post(
        "/api/auth/password",
        json={"current_password": "not-my-password", "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_password_change_rejects_short_passwords(client):
    make_user("ana@noetinger.test")
    login(client, "ana@noetinger.test")

    response = client.post(
        "/api/auth/password", json={"current_password": "secret-pass-1", "new_password": "short"}
    )

    assert response.status_code == 422


def test_password_change_signs_out_other_sessions_but_keeps_the_current_one(client):
    user = make_user("ana@noetinger.test")
    make_membership(user, make_municipality("Noetinger"))
    other_device = login(client, "ana@noetinger.test").cookies["g360_session"]
    client.cookies.clear()
    login(client, "ana@noetinger.test")

    client.post(
        "/api/auth/password",
        json={"current_password": "secret-pass-1", "new_password": NEW_PASSWORD},
    )

    assert client.get("/api/auth/me").status_code == 200
    client.cookies.clear()
    client.cookies.set("g360_session", other_device)
    assert client.get("/api/auth/me").status_code == 401
