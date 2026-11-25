"""Single sign-on through OpenID Connect: signs in existing accounts, and nothing else."""

import logging
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from gobernar360.core.config import get_settings
from gobernar360.main import create_app
from gobernar360.platform import sso
from gobernar360.platform.models import MunicipalitySettings, SsoLogin, User
from gobernar360.platform.models import Session as SessionRow
from tests.factories import (
    admin_session,
    configure,
    login,
    make_membership,
    make_municipality,
    make_user,
)
from tests.fake_oidc import CLIENT_ID, CLIENT_SECRET, ISSUER, FakeProvider, _new_key

CALLBACK = "/api/auth/sso/callback"


@pytest.fixture
def provider(client, monkeypatch):
    provider = FakeProvider()
    settings = get_settings()
    monkeypatch.setattr(settings, "oidc_issuer", ISSUER)
    monkeypatch.setattr(settings, "oidc_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "oidc_client_secret", CLIENT_SECRET)
    sso.clear_cache()

    def fake_http():
        with httpx2.Client(transport=provider.transport()) as http:
            yield http

    client.app.dependency_overrides[sso.get_http_client] = fake_http
    yield provider
    sso.clear_cache()


@pytest.fixture
def noetinger():
    """A municipality whose administrators allow single sign-on."""
    municipality = make_municipality("Noetinger")
    configure(municipality, sso=True)
    return municipality


@pytest.fixture
def ana(noetinger):
    user = make_user("ana@noetinger.test")
    make_membership(user, noetinger)
    return user


def _start(client) -> str:
    response = client.get("/api/auth/sso/start", follow_redirects=False)
    assert response.status_code == 302, response.text
    return response.headers["location"]


def _sign_in(client, provider, email="ana@noetinger.test", verified=True):
    answer = provider.authorize(_start(client), email, verified)
    return client.get(CALLBACK, params=answer, follow_redirects=False)


def _login_error(response) -> str | None:
    location = urlparse(response.headers["location"])
    return parse_qs(location.query).get("sso_error", [None])[0]


def _session_count() -> int:
    with admin_session() as session:
        return session.scalar(select(func.count()).select_from(SessionRow))


def test_sso_is_off_unless_configured(client):
    assert client.get("/api/auth/sso").json() == {"enabled": False}
    response = client.get("/api/auth/sso/start", follow_redirects=False)
    assert _login_error(response) == "disabled"


def test_sso_is_offered_when_configured_and_a_municipality_allows_it(client, provider):
    saira = make_municipality("Saira")
    configure(saira)

    before = client.get("/api/auth/sso").json()
    configure(make_municipality("Noetinger"), sso=True)
    after = client.get("/api/auth/sso").json()

    assert (before, after) == ({"enabled": False}, {"enabled": True})


def test_sso_is_not_offered_while_no_municipality_allows_it(client, provider):
    make_membership(make_user("ana@noetinger.test"), make_municipality("Noetinger"))

    response = client.get("/api/auth/sso/start", follow_redirects=False)

    assert _login_error(response) == "disabled"


def test_start_sends_the_browser_to_the_provider_with_pkce_state_and_nonce(
    client, provider, noetinger
):
    location = _start(client)

    query = {key: values[0] for key, values in parse_qs(urlparse(location).query).items()}
    assert location.startswith(f"{ISSUER}/authorize?")
    assert query["redirect_uri"] == "http://localhost:5173/api/auth/sso/callback"
    assert query["code_challenge_method"] == "S256"
    assert len(query["state"]) >= 32 and len(query["nonce"]) >= 32
    assert client.cookies.get("g360_sso") == query["state"]
    with admin_session() as session:
        attempt = session.scalars(select(SsoLogin)).one()
    # The state travels only in the browser's cookie; the server keeps its hash.
    assert attempt.state_hash != query["state"]
    assert sso.pkce_challenge(attempt.code_verifier) == query["code_challenge"]


def test_sso_signs_in_an_existing_account(client, provider, ana):
    response = _sign_in(client, provider)

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/"
    me = client.get("/api/auth/me").json()
    assert me["user"]["email"] == "ana@noetinger.test"
    # Like a password sign-in: the only municipality becomes the active one.
    assert me["active_municipality_id"] == me["memberships"][0]["municipality"]["id"]
    assert client.cookies.get("g360_sso") is None


def test_sso_matches_the_email_ignoring_case(client, provider, ana):
    _sign_in(client, provider, email="Ana@Noetinger.TEST")

    assert client.get("/api/auth/me").status_code == 200


def test_sso_rejects_a_wrong_state(client, provider, ana):
    answer = provider.authorize(_start(client), "ana@noetinger.test")

    response = client.get(
        CALLBACK, params=answer | {"state": "forged-state"}, follow_redirects=False
    )

    assert _login_error(response) == "failed"
    assert client.get("/api/auth/me").status_code == 401
    # The code was never even redeemed.
    assert provider.token_requests == []
    assert _session_count() == 0


def test_sso_rejects_a_callback_in_a_browser_that_did_not_start_it(client, provider, ana):
    # Someone starts a sign-in and tries to finish it in another person's browser.
    answer = provider.authorize(_start(client), "ana@noetinger.test")

    with TestClient(create_app()) as victim:
        victim.app.dependency_overrides = client.app.dependency_overrides
        response = victim.get(CALLBACK, params=answer, follow_redirects=False)

        assert _login_error(response) == "failed"
        assert victim.get("/api/auth/me").status_code == 401
    assert _session_count() == 0


def test_sso_rejects_an_unverified_email(client, provider, ana):
    response = _sign_in(client, provider, verified=False)

    assert _login_error(response) == "unverified_email"
    assert client.get("/api/auth/me").status_code == 401
    assert _session_count() == 0


def test_sso_never_creates_an_account(client, provider, ana):
    response = _sign_in(client, provider, email="desconocida@noetinger.test")

    assert _login_error(response) == "no_account"
    with admin_session() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
    assert _session_count() == 0


def test_sso_does_not_sign_in_a_deactivated_account(client, provider, noetinger):
    make_membership(make_user("ana@noetinger.test", active=False), noetinger)

    assert _login_error(_sign_in(client, provider)) == "no_account"


def test_an_sso_attempt_works_only_once(client, provider, ana):
    answer = provider.authorize(_start(client), "ana@noetinger.test")
    state_cookie = client.cookies.get("g360_sso")
    client.get(CALLBACK, params=answer, follow_redirects=False)
    client.post("/api/auth/logout")

    client.cookies.set("g360_sso", state_cookie, path="/api/auth/sso")
    replay = client.get(CALLBACK, params=answer, follow_redirects=False)

    assert _login_error(replay) == "failed"
    assert client.get("/api/auth/me").status_code == 401


def test_sso_rejects_an_id_token_with_another_nonce(client, provider, ana):
    provider.id_token_overrides = {"nonce": "from-another-sign-in"}

    assert _login_error(_sign_in(client, provider)) == "failed"
    assert _session_count() == 0


def test_sso_rejects_an_id_token_for_another_client(client, provider, ana):
    provider.id_token_overrides = {"aud": "someone-else"}

    assert _login_error(_sign_in(client, provider)) == "failed"


def test_sso_rejects_an_id_token_from_another_issuer(client, provider, ana):
    provider.id_token_overrides = {"iss": "https://evil.test"}

    assert _login_error(_sign_in(client, provider)) == "failed"


def test_sso_rejects_an_expired_id_token(client, provider, ana):
    provider.id_token_overrides = {"exp": 1_000_000_000}

    assert _login_error(_sign_in(client, provider)) == "failed"


def test_sso_rejects_an_id_token_signed_with_an_unpublished_key(client, provider, ana):
    provider.signing_key = _new_key()

    assert _login_error(_sign_in(client, provider)) == "failed"
    assert _session_count() == 0


def test_sso_reads_the_email_from_userinfo_when_the_id_token_lacks_it(client, provider, ana):
    provider.email_in_id_token = False

    _sign_in(client, provider)

    assert client.get("/api/auth/me").json()["user"]["email"] == "ana@noetinger.test"


def test_sso_checks_verification_in_userinfo_too(client, provider, ana):
    provider.email_in_id_token = False

    assert _login_error(_sign_in(client, provider, verified=False)) == "unverified_email"


def test_sso_reports_a_cancelled_sign_in(client, provider, ana):
    location = _start(client)
    state = parse_qs(urlparse(location).query)["state"][0]

    response = client.get(
        CALLBACK, params={"error": "access_denied", "state": state}, follow_redirects=False
    )

    assert _login_error(response) == "cancelled"


def test_an_unreachable_provider_sends_the_person_back_with_an_error(client, provider, noetinger):
    def unreachable(request):
        raise httpx2.ConnectError("connection refused", request=request)

    def broken_http():
        with httpx2.Client(transport=httpx2.MockTransport(unreachable)) as http:
            yield http

    client.app.dependency_overrides[sso.get_http_client] = broken_http

    response = client.get("/api/auth/sso/start", follow_redirects=False)

    assert _login_error(response) == "failed"


def test_sso_keeps_working_when_the_provider_replaces_its_key_under_the_same_id(
    client, provider, ana
):
    _sign_in(client, provider)  # the provider's keys are now cached
    client.post("/api/auth/logout")
    provider.key = _new_key()

    response = _sign_in(client, provider)

    assert response.headers["location"] == "http://localhost:5173/"
    assert client.get("/api/auth/me").status_code == 200


# Which municipalities allow it


def test_sso_refuses_someone_whose_municipalities_do_not_allow_it(client, provider, noetinger):
    make_membership(make_user("sara@saira.test"), make_municipality("Saira"))

    response = _sign_in(client, provider, email="sara@saira.test")

    assert _login_error(response) == "not_allowed"
    assert _session_count() == 0


def test_an_sso_session_only_reaches_municipalities_that_allow_it(client, provider, ana):
    saira = make_municipality("Saira")
    make_membership(ana, saira, grants={"demo": "viewer"})

    _sign_in(client, provider)
    me = client.get("/api/auth/me").json()
    switch = client.post("/api/auth/active-municipality", json={"municipality_id": str(saira.id)})

    assert [m["municipality"]["name"] for m in me["memberships"]] == ["Noetinger"]
    # The only municipality it may use becomes the active one.
    assert me["active_municipality_id"] == me["memberships"][0]["municipality"]["id"]
    assert switch.status_code == 403


def test_the_same_account_signed_in_with_its_password_reaches_every_municipality(
    client, provider, ana
):
    make_membership(ana, make_municipality("Saira"))

    me = login(client, "ana@noetinger.test").json()

    assert sorted(m["municipality"]["name"] for m in me["memberships"]) == ["Noetinger", "Saira"]


def test_turning_sso_off_cuts_the_sessions_it_opened(client, provider, ana, noetinger):
    _sign_in(client, provider)
    assert client.get("/api/overview").status_code == 200

    with admin_session() as session, session.begin():
        session.execute(
            update(MunicipalitySettings)
            .where(MunicipalitySettings.municipality_id == noetinger.id)
            .values(sso_enabled=False)
        )

    assert client.get("/api/overview").status_code == 403
    assert client.get("/api/auth/me").json()["memberships"] == []


def test_an_operator_signed_in_with_sso_does_not_operate_the_platform(client, provider, noetinger):
    operator = make_user("ana@noetinger.test", operator=True)
    make_membership(operator, noetinger)

    _sign_in(client, provider)

    assert client.get("/api/auth/me").json()["user"]["is_platform_operator"] is False
    assert client.get("/api/platform/municipalities").status_code == 403
    client.post("/api/auth/logout")
    login(client, "ana@noetinger.test")
    assert client.get("/api/platform/municipalities").status_code == 200


# What the server log says about each refusal


def _refusals(caplog) -> list[tuple[int, str]]:
    return [
        (record.levelno, record.getMessage())
        for record in caplog.records
        if record.name == "gobernar360.platform.sso_router"
    ]


@pytest.fixture
def sso_log(caplog):
    caplog.set_level(logging.INFO, logger="gobernar360.platform.sso_router")
    return caplog


def test_a_wrong_state_is_logged_as_a_failure(client, provider, ana, sso_log):
    answer = provider.authorize(_start(client), "ana@noetinger.test")

    response = client.get(CALLBACK, params=answer | {"state": "forged"}, follow_redirects=False)

    assert response.status_code == 302
    assert _refusals(sso_log) == [
        (
            logging.WARNING,
            "Single sign-on refused (failed): "
            "The state does not match the one this browser started with.",
        )
    ]


def test_a_callback_without_the_cookie_is_logged_as_a_failure(client, provider, ana, sso_log):
    answer = provider.authorize(_start(client), "ana@noetinger.test")
    client.cookies.clear()

    client.get(CALLBACK, params=answer, follow_redirects=False)

    assert _refusals(sso_log)[0][1].endswith("the one this browser started with.")


def test_a_replayed_attempt_is_logged_as_unknown(client, provider, ana, sso_log):
    answer = provider.authorize(_start(client), "ana@noetinger.test")
    state_cookie = client.cookies.get("g360_sso")
    client.get(CALLBACK, params=answer, follow_redirects=False)
    client.cookies.set("g360_sso", state_cookie, path="/api/auth/sso")
    sso_log.clear()

    client.get(CALLBACK, params=answer, follow_redirects=False)

    assert _refusals(sso_log) == [
        (logging.WARNING, "Single sign-on refused (failed): Unknown or expired sign-in attempt.")
    ]


def test_an_expired_attempt_is_refused(client, provider, ana, sso_log):
    answer = provider.authorize(_start(client), "ana@noetinger.test")
    with admin_session() as session, session.begin():
        session.execute(update(SsoLogin).values(expires_at=datetime.now(UTC)))

    response = client.get(CALLBACK, params=answer, follow_redirects=False)

    assert _login_error(response) == "failed"
    assert provider.token_requests == []
    assert _refusals(sso_log)[0][1].endswith("Unknown or expired sign-in attempt.")


def test_a_provider_error_other_than_a_cancellation_is_a_failure(client, provider, ana, sso_log):
    state = parse_qs(urlparse(_start(client)).query)["state"][0]

    response = client.get(
        CALLBACK, params={"error": "server_error", "state": state}, follow_redirects=False
    )

    assert _login_error(response) == "failed"
    assert _refusals(sso_log) == [
        (logging.WARNING, "Single sign-on refused (failed): server_error")
    ]


def test_a_cancelled_sign_in_is_only_information(client, provider, ana, sso_log):
    state = parse_qs(urlparse(_start(client)).query)["state"][0]

    client.get(CALLBACK, params={"error": "access_denied", "state": state}, follow_redirects=False)

    assert _refusals(sso_log) == [
        (logging.INFO, "Single sign-on refused (cancelled): access_denied")
    ]


def test_a_callback_without_a_code_is_a_failure(client, provider, ana, sso_log):
    state = parse_qs(urlparse(_start(client)).query)["state"][0]

    response = client.get(CALLBACK, params={"state": state}, follow_redirects=False)

    assert _login_error(response) == "failed"
    assert _refusals(sso_log) == [
        (
            logging.WARNING,
            "Single sign-on refused (failed): The provider sent no authorization code.",
        )
    ]


def test_the_reasons_about_the_person_are_logged_as_information(
    client, provider, noetinger, sso_log
):
    make_membership(make_user("ana@noetinger.test"), noetinger)
    make_membership(make_user("sara@saira.test"), make_municipality("Saira"))

    _sign_in(client, provider, verified=False)
    _sign_in(client, provider, email="nadie@noetinger.test")
    _sign_in(client, provider, email="sara@saira.test")

    assert _refusals(sso_log) == [
        (
            logging.INFO,
            "Single sign-on refused (unverified_email): ana@noetinger.test is not verified.",
        ),
        (
            logging.INFO,
            "Single sign-on refused (no_account): No active account for nadie@noetinger.test.",
        ),
        (
            logging.INFO,
            "Single sign-on refused (not_allowed): No municipality of sara@saira.test allows it.",
        ),
    ]


def test_a_provider_that_cannot_be_reached_is_logged_when_starting(
    client, provider, noetinger, sso_log
):
    def unreachable(request):
        raise httpx2.ConnectError("connection refused", request=request)

    def broken_http():
        with httpx2.Client(transport=httpx2.MockTransport(unreachable)) as http:
            yield http

    client.app.dependency_overrides[sso.get_http_client] = broken_http

    response = client.get("/api/auth/sso/start", follow_redirects=False)

    assert response.status_code == 302
    [(level, message)] = _refusals(sso_log)
    assert level == logging.WARNING
    assert message.startswith(
        f"Single sign-on could not start: Could not read {ISSUER}/.well-known/openid-configuration"
    )


def test_a_refused_sign_in_goes_back_to_the_login_page_with_a_redirect(client, provider, ana):
    response = client.get(CALLBACK, params={"state": "x"}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/login?sso_error=failed"


def test_coming_back_after_the_municipality_stopped_allowing_it_is_refused(
    client, provider, noetinger
):
    answer = provider.authorize(_start(client), "ana@noetinger.test", True)
    with admin_session() as session, session.begin():
        session.execute(update(MunicipalitySettings).values(sso_enabled=False))

    response = client.get(CALLBACK, params=answer, follow_redirects=False)

    assert _login_error(response) == "disabled"
    assert _session_count() == 0
