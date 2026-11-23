"""Invitation and recovery links: single use, expiring, stored only as hashes."""

import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text, update

from gobernar360.core.db import platform_session
from gobernar360.core.errors import ApiError
from gobernar360.core.security import hash_token
from gobernar360.platform import accounts
from gobernar360.platform.models import AccountToken, PasswordResetRequest
from gobernar360.platform.texts import format_datetime
from tests.factories import (
    admin_session,
    emails_to,
    link_token,
    login,
    make_membership,
    make_municipality,
    make_user,
)

NEW_PASSWORD = "a-brand-new-password"


@pytest.fixture
def invited(client):
    """An account invited by an administrator, with its invitation link."""
    noetinger = make_municipality("Noetinger")
    make_membership(make_user("admin@noetinger.test"), noetinger, admin=True)
    login(client, "admin@noetinger.test")
    client.post("/api/admin/users", json={"email": "carla@noetinger.test", "full_name": "Carla"})
    client.post("/api/auth/logout")
    return link_token(emails_to("carla@noetinger.test")[-1])


def _redeem(client, token, password=NEW_PASSWORD):
    return client.post("/api/auth/tokens/redeem", json={"token": token, "password": password})


def _inspect(client, token):
    return client.post("/api/auth/tokens/inspect", json={"token": token})


def _forgot(client, email):
    return client.post("/api/auth/password-reset", json={"email": email})


def _expire_every_link():
    with admin_session() as session, session.begin():
        session.execute(
            update(AccountToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )


def test_invitation_link_sets_the_password_then_stops_working(client, invited):
    assert _inspect(client, invited).json() == {
        "purpose": "invitation",
        "email": "carla@noetinger.test",
        "full_name": "Carla",
    }

    first = _redeem(client, invited)
    again = _redeem(client, invited, "yet-another-password")

    assert first.status_code == 204
    assert again.status_code == 410
    assert again.json()["error"]["code"] == "invalid_token"
    assert _inspect(client, invited).status_code == 410
    login(client, "carla@noetinger.test", NEW_PASSWORD)


def test_looking_at_a_link_does_not_use_it_up(client, invited):
    _inspect(client, invited)
    _inspect(client, invited)

    assert _redeem(client, invited).status_code == 204


def test_expired_link_is_rejected(client, invited):
    _expire_every_link()

    assert _inspect(client, invited).status_code == 410
    assert _redeem(client, invited).status_code == 410
    signed_in = client.post(
        "/api/auth/login", json={"email": "carla@noetinger.test", "password": NEW_PASSWORD}
    )
    assert signed_in.status_code == 401


def test_unknown_link_is_rejected(client):
    assert _redeem(client, "made-up-token").status_code == 410


def test_link_token_is_stored_only_as_its_hash(client, invited):
    with admin_session() as session:
        rows = session.scalars(select(AccountToken)).all()
        dump = session.execute(text("SELECT account_tokens::text FROM account_tokens")).scalars()
        dump = " ".join(dump)
    assert [row.token_hash for row in rows] == [hash_token(invited)]
    assert invited not in dump


def test_short_password_is_rejected_and_the_link_still_works(client, invited):
    assert _redeem(client, invited, "short").status_code == 422
    assert _redeem(client, invited).status_code == 204


def test_link_of_a_deactivated_account_does_not_work(client, invited):
    with admin_session() as session, session.begin():
        session.execute(text("UPDATE users SET is_active = false"))

    assert _inspect(client, invited).status_code == 410
    assert _redeem(client, invited).status_code == 410


def test_two_simultaneous_uses_of_one_link_set_only_one_password(client, invited):
    results: list[str] = []

    def use(password: str, hold: float) -> None:
        try:
            with platform_session() as db:
                accounts.redeem_token(db, invited, password)
                # Keep the first transaction open while the second one tries.
                time.sleep(hold)
            results.append(password)
        except ApiError as error:
            results.append(error.code)

    first = threading.Thread(target=use, args=("first-password-1", 0.5))
    second = threading.Thread(target=use, args=("second-password-2", 0))
    first.start()
    time.sleep(0.2)
    second.start()
    first.join()
    second.join()

    assert sorted(results) == ["first-password-1", "invalid_token"]
    login(client, "carla@noetinger.test", "first-password-1")


# Password recovery


def test_recovery_answers_identically_for_known_and_unknown_emails(client):
    make_user("ana@noetinger.test")

    known = _forgot(client, "ana@noetinger.test")
    unknown = _forgot(client, "nadie@noetinger.test")

    assert known.status_code == unknown.status_code == 204
    assert known.content == unknown.content == b""
    assert known.headers.keys() == unknown.headers.keys()
    assert "set-cookie" not in known.headers
    assert len(emails_to("ana@noetinger.test")) == 1
    assert emails_to("nadie@noetinger.test") == []


def test_recovery_link_sets_a_new_password_and_closes_every_session(client):
    make_user("ana@noetinger.test")
    first_device = login(client, "ana@noetinger.test").cookies["g360_session"]
    client.cookies.clear()
    second_device = login(client, "ana@noetinger.test").cookies["g360_session"]
    client.cookies.clear()

    _forgot(client, "ana@noetinger.test")
    [email] = emails_to("ana@noetinger.test")
    response = _redeem(client, link_token(email))

    assert response.status_code == 204
    assert email.subject == "Elegí una contraseña nueva para gobernar360"
    for cookie in (first_device, second_device):
        client.cookies.clear()
        client.cookies.set("g360_session", cookie)
        assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    old = client.post(
        "/api/auth/login", json={"email": "ana@noetinger.test", "password": "secret-pass-1"}
    )
    assert old.status_code == 401
    login(client, "ana@noetinger.test", NEW_PASSWORD)


def test_recovery_is_rate_limited_per_address_whether_or_not_it_exists(client):
    make_user("ana@noetinger.test")

    known = [_forgot(client, "ana@noetinger.test").status_code for _ in range(4)]
    unknown = [_forgot(client, "nadie@noetinger.test").status_code for _ in range(4)]
    other = _forgot(client, "otra@noetinger.test")

    assert known == unknown == [204, 204, 204, 429]
    assert known[-1] == 429
    assert _forgot(client, "ana@noetinger.test").json()["error"]["code"] == "too_many_requests"
    assert other.status_code == 204
    assert len(emails_to("ana@noetinger.test")) == 3


def test_rate_limit_ignores_case_and_spaces_and_frees_up_after_the_window(client):
    make_user("ana@noetinger.test")
    for _ in range(3):
        _forgot(client, "ana@noetinger.test")

    assert _forgot(client, " Ana@Noetinger.TEST ").status_code == 429
    with admin_session() as session, session.begin():
        session.execute(
            update(PasswordResetRequest).values(
                created_at=datetime.now(UTC) - timedelta(minutes=61)
            )
        )
    assert _forgot(client, "ana@noetinger.test").status_code == 204


def test_recovery_requests_store_no_email_address(client):
    _forgot(client, "nadie@noetinger.test")

    with admin_session() as session:
        dump = " ".join(
            session.execute(
                text("SELECT password_reset_requests::text FROM password_reset_requests")
            ).scalars()
        )
    assert "nadie" not in dump


def test_a_new_recovery_link_replaces_the_previous_one(client):
    make_user("ana@noetinger.test")
    _forgot(client, "ana@noetinger.test")
    _forgot(client, "ana@noetinger.test")

    older, newer = emails_to("ana@noetinger.test")

    assert _redeem(client, link_token(older)).status_code == 410
    assert _redeem(client, link_token(newer)).status_code == 204


def test_changing_the_password_cancels_a_pending_recovery_link(client):
    make_user("ana@noetinger.test")
    _forgot(client, "ana@noetinger.test")
    login(client, "ana@noetinger.test")
    client.post(
        "/api/auth/password",
        json={"current_password": "secret-pass-1", "new_password": NEW_PASSWORD},
    )

    stale = _redeem(client, link_token(emails_to("ana@noetinger.test")[0]), "attacker-password")

    assert stale.status_code == 410


def test_recovery_sends_nothing_to_a_deactivated_account(client):
    make_user("ana@noetinger.test", active=False)

    assert _forgot(client, "ana@noetinger.test").status_code == 204
    assert emails_to("ana@noetinger.test") == []


def test_recovery_lets_an_invited_account_choose_its_first_password(client):
    make_user("ana@noetinger.test", password=None)

    _forgot(client, "ana@noetinger.test")
    [email] = emails_to("ana@noetinger.test")

    assert _redeem(client, link_token(email)).status_code == 204
    login(client, "ana@noetinger.test", NEW_PASSWORD)


def test_recovery_rejects_a_malformed_email(client):
    assert _forgot(client, "not-an-email").status_code == 422


def test_account_without_a_password_cannot_sign_in(client):
    make_user("ana@noetinger.test", password=None)

    for password in ("", "anything-at-all"):
        response = client.post(
            "/api/auth/login", json={"email": "ana@noetinger.test", "password": password}
        )
        assert response.status_code == 401


def _tokens(email: str) -> list[tuple[str, datetime, datetime | None]]:
    with admin_session() as session:
        rows = session.execute(
            text(
                "SELECT t.purpose, t.expires_at, t.used_at FROM account_tokens t "
                "JOIN users u ON u.id = t.user_id WHERE u.email = :email ORDER BY t.created_at"
            ),
            {"email": email},
        ).all()
    return [tuple(row) for row in rows]


def test_each_kind_of_link_lasts_its_own_time(client, invited):
    make_user("ana@noetinger.test")
    before = datetime.now(UTC)
    _forgot(client, "ana@noetinger.test")

    [(purpose, expires_at, _)] = _tokens("ana@noetinger.test")
    [(invitation, invitation_expires, _)] = _tokens("carla@noetinger.test")

    assert purpose == "password_reset"
    assert before + timedelta(minutes=59) < expires_at <= datetime.now(UTC) + timedelta(hours=1)
    assert invitation == "invitation"
    assert invitation_expires > datetime.now(UTC) + timedelta(days=6, hours=23)


def test_a_recovery_link_leaves_a_pending_invitation_working(client, invited):
    _forgot(client, "carla@noetinger.test")

    purposes = [
        (purpose, used_at is None) for purpose, _, used_at in _tokens("carla@noetinger.test")
    ]

    assert purposes == [("invitation", True), ("password_reset", True)]
    assert _redeem(client, invited).status_code == 204


def test_requests_older_than_the_window_are_forgotten(client):
    make_user("ana@noetinger.test")
    _forgot(client, "ana@noetinger.test")
    _forgot(client, "nadie@noetinger.test")
    with admin_session() as session, session.begin():
        session.execute(
            update(PasswordResetRequest).values(
                created_at=datetime.now(UTC) - timedelta(minutes=61)
            )
        )

    _forgot(client, "otra@noetinger.test")

    with admin_session() as session:
        assert session.scalar(select(func.count()).select_from(PasswordResetRequest)) == 1


def test_the_recovery_email_greets_the_person_and_says_when_the_link_expires(client):
    make_user("ana@noetinger.test")
    before = datetime.now(UTC)

    _forgot(client, "ana@noetinger.test")

    [email] = emails_to("ana@noetinger.test")
    assert email.body.startswith("Hola, Ana:\n")
    expiry = {format_datetime(before + timedelta(minutes=60 + extra)) for extra in (0, 1)}
    assert any(f"vence el {moment}." in email.body for moment in expiry)


def test_a_link_for_one_account_leaves_the_links_of_others_alone(client):
    make_user("ana@noetinger.test")
    make_user("beto@noetinger.test")
    _forgot(client, "ana@noetinger.test")

    _forgot(client, "beto@noetinger.test")

    assert _redeem(client, link_token(emails_to("ana@noetinger.test")[0])).status_code == 204
