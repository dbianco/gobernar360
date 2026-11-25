"""The session cookie, who may open a session, and who is said to have changed what."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from gobernar360.core import security
from gobernar360.core.config import get_settings
from gobernar360.platform.access import SESSION_COOKIE
from gobernar360.platform.models import Session as SessionRow
from tests.economic.factories import economic_member, make_actor
from tests.factories import (
    DEFAULT_PASSWORD,
    admin_session,
    login,
    make_membership,
    make_municipality,
    make_user,
)

EMAIL = "ana@noetinger.test"


def _cookie(client) -> dict[str, str]:
    """The attributes the session cookie was set with, by lowercase name."""
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": DEFAULT_PASSWORD})
    assert response.status_code == 200, response.text
    [header] = [
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(f"{SESSION_COOKIE}=")
    ]
    parts = [part.strip().partition("=") for part in header.split(";")[1:]]
    return {name.lower(): value for name, _, value in parts}


@pytest.mark.parametrize(("secure", "hours"), [(False, 12), (True, 2)])
def test_the_session_cookie_stays_in_the_browser_and_in_this_site(
    client, monkeypatch, secure, hours
):
    monkeypatch.setattr(get_settings(), "cookie_secure", secure)
    monkeypatch.setattr(get_settings(), "session_ttl_hours", hours)
    make_membership(make_user(EMAIL), make_municipality())

    cookie = _cookie(client)

    assert "httponly" in cookie
    assert ("secure" in cookie) is secure
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"
    assert cookie["max-age"] == str(hours * 3600)
    with admin_session() as session:
        expires = session.scalars(select(SessionRow.expires_at)).one()
    assert abs(expires - datetime.now(UTC) - timedelta(hours=hours)) < timedelta(minutes=1)


@pytest.mark.parametrize(("left", "status"), [(-60, 401), (60, 200)])
def test_a_session_ends_when_its_time_is_over(client, left, status):
    make_membership(make_user(EMAIL), make_municipality())
    login(client, EMAIL)
    with admin_session() as session, session.begin():
        moment = datetime.now(UTC) + timedelta(seconds=left)
        session.execute(update(SessionRow).values(expires_at=moment))

    assert client.get("/api/auth/me").status_code == status


def test_an_account_without_a_password_cannot_be_signed_in_to(client):
    """The password the dummy hash is made of opens nothing either."""
    make_membership(make_user(EMAIL, password=None), make_municipality())

    for password in ("not-a-real-password", "", DEFAULT_PASSWORD):
        response = client.post("/api/auth/login", json={"email": EMAIL, "password": password})
        assert response.status_code in (401, 422), password
    assert security.verify_password("not-a-real-password", None) is False
    assert security.verify_password("x", security.hash_password("x")) is True
    assert security.verify_password("y", security.hash_password("x")) is False


def test_tokens_are_long_and_never_repeat():
    tokens = [security.new_token() for _ in range(50)]

    assert len({token for token, _ in tokens}) == 50
    for token, digest in tokens:
        # 32 random bytes.
        assert len(token) == 43
        assert digest == security.hash_token(token)


def test_who_changes_a_record_is_not_said_to_have_created_it(client):
    municipality = economic_member("editor")
    carla = make_user("carla@noetinger.test")
    make_membership(carla, municipality, grants={"economic": "editor"})
    login(client, EMAIL)
    created = client.post("/api/dashboards/economic/actors", json={"name": "Taller"}).json()
    client.post("/api/auth/logout")
    login(client, "carla@noetinger.test")

    client.patch(f"/api/dashboards/economic/actors/{created['id']}", json={"name": "Otro"})

    with admin_session() as session:
        actor = session.get(type(make_actor(municipality)), created["id"])
        assert actor.created_by is not None and actor.created_by != carla.id
        assert actor.updated_by == carla.id
        assert actor.updated_at > actor.created_at
