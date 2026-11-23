"""Single sign-on routes: leave for the OpenID Connect provider and come back signed in.

The browser goes to /start, which remembers the attempt (state, nonce, PKCE verifier)
and sends it to the provider; the provider sends it back to /callback. The `state` in the
callback must equal the one in the cookie /start set on that same browser, which stops
anyone from completing a sign-in in someone else's browser, and each attempt works once.

Only accounts that already exist are signed in, matched by an email the provider says it
verified, and only into municipalities whose administrators allow single sign-on (none
do by default). No account is ever created here.
"""

import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx2
from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, select

from gobernar360.core.config import get_settings
from gobernar360.core.security import hash_token, normalize_email
from gobernar360.platform.access import SSO, Db
from gobernar360.platform.auth_router import start_session
from gobernar360.platform.models import Membership, SsoLogin, User
from gobernar360.platform.municipality_settings import sso_municipality_ids
from gobernar360.platform.sso import OidcClient, SsoError, get_http_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/sso", tags=["auth"])

SSO_COOKIE = "g360_sso"
COOKIE_PATH = "/api/auth/sso"
CALLBACK_PATH = "/api/auth/sso/callback"
ATTEMPT_LIFETIME = timedelta(minutes=10)

Http = Annotated[httpx2.Client, Depends(get_http_client)]


class SsoOptions(BaseModel):
    enabled: bool


def _offered(db: Db) -> bool:
    """A provider is configured and at least one municipality allows single sign-on."""
    return get_settings().sso_enabled and bool(sso_municipality_ids(db))


def _redirect_uri() -> str:
    return get_settings().app_link(CALLBACK_PATH)


def _back_to_login(code: str) -> RedirectResponse:
    return RedirectResponse(get_settings().app_link(f"/login?sso_error={code}"), status_code=302)


@router.get("")
def sso_options(db: Db) -> SsoOptions:
    """Whether the sign-in page offers single sign-on."""
    return SsoOptions(enabled=_offered(db))


@router.get("/start")
def start(db: Db, http: Http) -> RedirectResponse:
    settings = get_settings()
    if not _offered(db):
        return _back_to_login("disabled")
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    try:
        url = OidcClient(settings, http).authorization_url(state, nonce, verifier, _redirect_uri())
    except SsoError as error:
        logger.warning("Single sign-on could not start: %s", error)
        return _back_to_login(error.code)
    now = datetime.now(UTC)
    db.execute(delete(SsoLogin).where(SsoLogin.expires_at < now))
    db.add(
        SsoLogin(
            state_hash=hash_token(state),
            nonce=nonce,
            code_verifier=verifier,
            expires_at=now + ATTEMPT_LIFETIME,
        )
    )
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        SSO_COOKIE,
        state,
        max_age=int(ATTEMPT_LIFETIME.total_seconds()),
        httponly=True,
        # Lax cookies travel on the provider's top-level redirect back to the callback.
        samesite="lax",
        secure=settings.cookie_secure,
        path=COOKIE_PATH,
    )
    return response


def _complete(
    db: Db, http: httpx2.Client, code: str | None, state: str | None, error: str | None, cookie
) -> User:
    if not state or not cookie or not hmac.compare_digest(state, cookie):
        raise SsoError("failed", "The state does not match the one this browser started with.")
    # Used up whatever happens next.
    attempt = db.scalar(
        delete(SsoLogin).where(SsoLogin.state_hash == hash_token(state)).returning(SsoLogin)
    )
    if attempt is None or attempt.expires_at <= datetime.now(UTC):
        raise SsoError("failed", "Unknown or expired sign-in attempt.")
    if error:
        raise SsoError("cancelled" if error == "access_denied" else "failed", error)
    if not code:
        raise SsoError("failed", "The provider sent no authorization code.")
    identity = OidcClient(get_settings(), http).identity(
        code, attempt.code_verifier, _redirect_uri(), attempt.nonce
    )
    if not identity.email_verified:
        raise SsoError("unverified_email", f"{identity.email} is not verified.")
    user = db.scalar(select(User).where(User.email == normalize_email(identity.email)))
    if user is None or not user.is_active:
        raise SsoError("no_account", f"No active account for {identity.email}.")
    municipalities = set(
        db.scalars(select(Membership.municipality_id).where(Membership.user_id == user.id))
    )
    if not municipalities & sso_municipality_ids(db):
        raise SsoError("not_allowed", f"No municipality of {identity.email} allows it.")
    return user


@router.get("/callback")
def callback(
    db: Db,
    http: Http,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    cookie: Annotated[str | None, Cookie(alias=SSO_COOKIE)] = None,
) -> RedirectResponse:
    try:
        if not _offered(db):
            raise SsoError("disabled")
        user = _complete(db, http, code, state, error, cookie)
    except SsoError as failure:
        # "failed" points at configuration or the provider; the rest are about the person.
        log = logger.warning if failure.code == "failed" else logger.info
        log("Single sign-on refused (%s): %s", failure.code, failure)
        response = _back_to_login(failure.code)
    else:
        response = RedirectResponse(get_settings().app_link("/"), status_code=302)
        start_session(db, user, response, auth_method=SSO)
    response.delete_cookie(SSO_COOKIE, path=COOKIE_PATH)
    return response
