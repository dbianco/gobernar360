"""Regression tests for findings of the final review."""

import pytest
from sqlalchemy import update

from gobernar360.platform.models import User
from tests.factories import (
    accept_invitation,
    admin_session,
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


ACCOUNT = "/api/auth/account"


def _signed_in_ana(client):
    user = make_user("ana@noetinger.test")
    make_membership(user, make_municipality("Noetinger"))
    login(client, "ana@noetinger.test")
    return user


def _stored(user_id) -> User:
    with admin_session() as session:
        return session.get(User, user_id)


def test_user_changes_their_name_and_phone_keeping_their_password(client):
    user = _signed_in_ana(client)

    response = client.put(
        ACCOUNT,
        json={
            "current_password": "secret-pass-1",
            "full_name": "  Ana María Gómez ",
            "phone": " +54 9 3472 15-123456 ",
        },
    )

    assert response.status_code == 200
    assert response.json()["user"]["full_name"] == "Ana María Gómez"
    assert response.json()["user"]["phone"] == "+54 9 3472 15-123456"
    assert response.json()["memberships"][0]["municipality"]["name"] == "Noetinger"
    stored = _stored(user.id)
    assert (stored.full_name, stored.phone) == ("Ana María Gómez", "+54 9 3472 15-123456")
    assert client.get("/api/auth/me").json()["user"]["phone"] == "+54 9 3472 15-123456"
    client.post("/api/auth/logout")
    login(client, "ana@noetinger.test")


def test_user_changes_their_password_with_the_rest_of_their_account(client):
    _signed_in_ana(client)
    other_device = client.cookies["g360_session"]
    client.cookies.clear()
    login(client, "ana@noetinger.test")

    response = client.put(
        ACCOUNT,
        json={
            "current_password": "secret-pass-1",
            "full_name": "Ana",
            "phone": "",
            "new_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    assert (
        client.post(
            "/api/auth/login", json={"email": "ana@noetinger.test", "password": "secret-pass-1"}
        ).status_code
        == 401
    )
    login(client, "ana@noetinger.test", NEW_PASSWORD)
    # The other session was signed out.
    client.cookies.clear()
    client.cookies.set("g360_session", other_device)
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize(
    "password_change", [{}, {"new_password": NEW_PASSWORD}], ids=["profile", "with password"]
)
def test_no_account_change_is_saved_without_the_current_password(client, password_change):
    user = _signed_in_ana(client)

    response = client.put(
        ACCOUNT,
        json={"current_password": "not-my-password", "full_name": "Otra", "phone": "123"}
        | password_change,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "invalid_credentials"
    stored = _stored(user.id)
    assert (stored.full_name, stored.phone) == ("Ana", "")
    client.post("/api/auth/logout")
    login(client, "ana@noetinger.test")


@pytest.mark.parametrize(
    "fields",
    [
        {"full_name": "   "},
        {"phone": "llamar al 123"},
        {"phone": "1" * 51},
        {"new_password": "short"},
    ],
)
def test_an_invalid_account_change_is_rejected(client, fields):
    user = _signed_in_ana(client)
    body = {"current_password": "secret-pass-1", "full_name": "Ana Gómez", "phone": ""} | fields

    response = client.put(ACCOUNT, json=body)

    assert response.status_code == 422
    assert _stored(user.id).full_name == "Ana"


def test_changing_the_account_needs_a_session(client):
    make_user("ana@noetinger.test")

    response = client.put(
        ACCOUNT, json={"current_password": "secret-pass-1", "full_name": "X", "phone": ""}
    )

    assert response.status_code == 401


def _signed_in_without_a_password(client) -> User:
    """Someone who only ever signed in through single sign-on: the account has no password."""
    user = _signed_in_ana(client)
    with admin_session() as session, session.begin():
        session.get(User, user.id).password_hash = None
    return user


def test_the_profile_says_whether_the_account_has_a_password(client):
    _signed_in_ana(client)
    assert client.get("/api/auth/me").json()["has_password"] is True

    with admin_session() as session, session.begin():
        session.execute(update(User).values(password_hash=None))

    assert client.get("/api/auth/me").json()["has_password"] is False


def test_an_account_without_a_password_changes_its_name_and_phone(client):
    user = _signed_in_without_a_password(client)

    response = client.put(ACCOUNT, json={"full_name": "Ana María Gómez", "phone": "3472 123456"})

    assert response.status_code == 200
    assert response.json()["user"]["full_name"] == "Ana María Gómez"
    stored = _stored(user.id)
    assert (stored.full_name, stored.phone) == ("Ana María Gómez", "3472 123456")


def test_an_account_without_a_password_gets_one_only_through_a_link(client):
    user = _signed_in_without_a_password(client)

    response = client.put(
        ACCOUNT, json={"full_name": "Otra", "phone": "", "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "validation_error",
        "message": "An account without a password chooses one through the link sent by email.",
    }
    stored = _stored(user.id)
    assert (stored.full_name, stored.password_hash) == ("Ana", None)


def test_an_account_with_a_password_still_needs_it_when_none_is_sent(client):
    user = _signed_in_ana(client)

    response = client.put(ACCOUNT, json={"full_name": "Otra", "phone": ""})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert _stored(user.id).full_name == "Ana"
