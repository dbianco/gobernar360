"""Regression tests for findings of the final review."""

from tests.factories import (
    accept_invitation,
    emails_to,
    login,
    make_membership,
    make_municipality,
    make_user,
)

NEW_PASSWORD = "a-brand-new-password"


def _operator(client):
    make_user("operator@gobernar360.test", operator=True)
    login(client, "operator@gobernar360.test")


def _add_to(client, municipality, **fields):
    return client.post(
        f"/api/platform/municipalities/{municipality.id}/users",
        json={"email": "intendente@beta.test", "full_name": "X"} | fields,
    )


def test_adding_an_existing_account_keeps_its_password_and_sessions(client):
    # Whoever adds an account that already exists gets no way into it: no password is
    # asked or changed, and the owner only receives a notice.
    make_user("intendente@beta.test", password="chosen-by-its-owner")
    beta = make_municipality("Beta")
    session_cookie = login(client, "intendente@beta.test", "chosen-by-its-owner").cookies[
        "g360_session"
    ]
    client.cookies.clear()
    _operator(client)

    response = _add_to(client, beta, password=NEW_PASSWORD, is_admin=True)

    assert response.status_code == 201
    client.cookies.clear()
    client.cookies.set("g360_session", session_cookie)
    assert client.get("/api/auth/me").json()["memberships"][0]["municipality"]["name"] == "Beta"
    client.post("/api/auth/logout")
    login(client, "intendente@beta.test", "chosen-by-its-owner")
    [notice] = emails_to("intendente@beta.test")
    assert "Beta" in notice.subject
    assert "/set-password" not in notice.body


def test_adding_an_account_that_never_chose_a_password_sends_it_a_new_invitation(client):
    make_user("intendente@beta.test", password=None)
    beta = make_municipality("Beta")
    _operator(client)

    _add_to(client, beta)
    client.post("/api/auth/logout")

    [invitation] = emails_to("intendente@beta.test")
    assert "/set-password#" in invitation.body
    accept_invitation(client, "intendente@beta.test", NEW_PASSWORD)
    assert login(client, "intendente@beta.test", NEW_PASSWORD).json()["memberships"]


def test_operator_adds_themselves_to_a_municipality_and_stays_signed_in(client):
    beta = make_municipality("Beta")
    _operator(client)

    response = client.post(
        f"/api/platform/municipalities/{beta.id}/users",
        json={"email": "operator@gobernar360.test", "full_name": "Operator", "is_admin": True},
    )

    assert response.status_code == 201
    assert client.get("/api/auth/me").json()["memberships"][0]["is_admin"] is True


def test_operator_adding_someone_who_is_already_a_member_changes_nothing(client):
    beta = make_municipality("Beta")
    make_membership(make_user("intendente@beta.test"), beta, admin=True)
    _operator(client)

    response = client.post(
        f"/api/platform/municipalities/{beta.id}/users",
        json={"email": "intendente@beta.test", "full_name": "X"},
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
