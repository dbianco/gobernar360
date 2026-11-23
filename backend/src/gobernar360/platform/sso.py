"""Single sign-on through an OpenID Connect provider: the client side of the protocol.

Authorization code flow with PKCE (S256). The provider is found through its discovery
document, its ID tokens are checked against its published keys, and the token's nonce
must be the one this sign-in attempt sent. Which account to open, and whether to, is
decided by the router.
"""

import base64
import hashlib
import hmac
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx2
import jwt

from gobernar360.core.config import Settings

# Asymmetric algorithms only: an HMAC-signed token would be checked with the client
# secret, which is not a proof that the provider issued it.
ALLOWED_ALGORITHMS = [
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
]
CACHE_SECONDS = 600
CLOCK_LEEWAY_SECONDS = 60


class SsoError(Exception):
    """A sign-in that cannot go on. `code` is what the sign-in page explains to the person."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code


@dataclass(frozen=True)
class ProviderMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str | None
    token_auth_methods: tuple[str, ...]


@dataclass(frozen=True)
class Identity:
    email: str
    email_verified: bool


# Discovery documents and key sets, by URL, with the time they were fetched.
_cache: dict[str, tuple[float, Any]] = {}


def clear_cache() -> None:
    _cache.clear()


def get_http_client() -> Iterator[httpx2.Client]:
    """FastAPI dependency, so tests can put a fake provider behind it."""
    with httpx2.Client(timeout=10, follow_redirects=False) as client:
        yield client


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _is_true(value: object) -> bool:
    # Some providers send the claim as the string "true".
    return value is True or value == "true"


class OidcClient:
    def __init__(self, settings: Settings, http: httpx2.Client) -> None:
        self.settings = settings
        self.http = http
        self.issuer = settings.oidc_issuer.rstrip("/")

    def _get_json(self, url: str, cached: bool = True) -> Any:
        hit = _cache.get(url)
        if cached and hit and time.monotonic() - hit[0] < CACHE_SECONDS:
            return hit[1]
        try:
            response = self.http.get(url, headers={"Accept": "application/json"})
            response.raise_for_status()
            document = response.json()
        except (httpx2.HTTPError, ValueError) as error:
            raise SsoError("failed", f"Could not read {url}: {error}") from error
        _cache[url] = (time.monotonic(), document)
        return document

    def metadata(self) -> ProviderMetadata:
        document = self._get_json(f"{self.issuer}/.well-known/openid-configuration")
        try:
            metadata = ProviderMetadata(
                issuer=document["issuer"],
                authorization_endpoint=document["authorization_endpoint"],
                token_endpoint=document["token_endpoint"],
                jwks_uri=document["jwks_uri"],
                userinfo_endpoint=document.get("userinfo_endpoint"),
                token_auth_methods=tuple(
                    document.get("token_endpoint_auth_methods_supported", ["client_secret_basic"])
                ),
            )
        except (KeyError, TypeError) as error:
            raise SsoError("failed", f"Incomplete discovery document: {error}") from error
        # The issuer in the document must be the configured one (OpenID Connect Discovery 4.3).
        if metadata.issuer.rstrip("/") != self.issuer:
            raise SsoError("failed", f"Discovery names issuer {metadata.issuer}")
        return metadata

    def authorization_url(self, state: str, nonce: str, verifier: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.oidc_client_id,
                "redirect_uri": redirect_uri,
                "scope": self.settings.oidc_scopes,
                "state": state,
                "nonce": nonce,
                "code_challenge": pkce_challenge(verifier),
                "code_challenge_method": "S256",
            }
        )
        endpoint = self.metadata().authorization_endpoint
        return f"{endpoint}{'&' if '?' in endpoint else '?'}{query}"

    def _exchange(self, metadata: ProviderMetadata, code: str, verifier: str, redirect_uri: str):
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }
        auth = None
        client_id, secret = self.settings.oidc_client_id, self.settings.oidc_client_secret
        if secret and "client_secret_basic" in metadata.token_auth_methods:
            # RFC 6749 2.3.1: both parts are form-encoded before going into the header.
            auth = (urlencode({"": client_id})[1:], urlencode({"": secret})[1:])
        else:
            form["client_id"] = client_id
            if secret:
                form["client_secret"] = secret
        try:
            response = self.http.post(
                metadata.token_endpoint,
                data=form,
                auth=auth,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            tokens = response.json()
        except (httpx2.HTTPError, ValueError) as error:
            raise SsoError("failed", f"Token request failed: {error}") from error
        if not isinstance(tokens, dict) or not tokens.get("id_token"):
            raise SsoError("failed", "The token response has no ID token.")
        return tokens

    def _signing_key(
        self, metadata: ProviderMetadata, header: dict[str, Any], cached: bool
    ) -> tuple[jwt.PyJWK, bool]:
        """The provider's key for this token, and whether it came from the cache."""
        kid = header.get("kid")
        for use_cache in (True, False) if cached else (False,):
            # An unknown key id may mean the provider rotated its keys: fetch them again.
            keys = self._get_json(metadata.jwks_uri, cached=use_cache).get("keys", [])
            matching = [key for key in keys if kid is None or key.get("kid") == kid]
            if kid is None and len(matching) != 1:
                break
            if matching:
                try:
                    return jwt.PyJWK(matching[0], algorithm=header["alg"]), use_cache
                except jwt.PyJWTError as error:
                    raise SsoError("failed", f"Unusable signing key: {error}") from error
        raise SsoError("failed", f"No signing key {kid} at the provider.")

    def _verify_id_token(self, metadata: ProviderMetadata, id_token: str, nonce: str) -> dict:
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError as error:
            raise SsoError("failed", f"Malformed ID token: {error}") from error
        if header.get("alg") not in ALLOWED_ALGORITHMS:
            raise SsoError("failed", f"ID token signed with {header.get('alg')}.")
        from_cache = True
        while True:
            key, from_cache = self._signing_key(metadata, header, cached=from_cache)
            try:
                claims = jwt.decode(
                    id_token,
                    key=key.key,
                    algorithms=[header["alg"]],
                    audience=self.settings.oidc_client_id,
                    issuer=metadata.issuer,
                    leeway=CLOCK_LEEWAY_SECONDS,
                    options={"require": ["iss", "aud", "exp", "iat", "sub"]},
                )
                break
            except jwt.InvalidSignatureError as error:
                # A provider may replace a key and keep its id: try once with fresh keys.
                if from_cache:
                    from_cache = False
                    continue
                raise SsoError("failed", f"Invalid ID token: {error}") from error
            except jwt.PyJWTError as error:
                raise SsoError("failed", f"Invalid ID token: {error}") from error
        audiences = claims["aud"] if isinstance(claims["aud"], list) else [claims["aud"]]
        if len(audiences) > 1 and claims.get("azp") != self.settings.oidc_client_id:
            raise SsoError("failed", "ID token issued to another party.")
        if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise SsoError("failed", "ID token nonce does not match this sign-in.")
        return claims

    def _userinfo(self, metadata: ProviderMetadata, access_token: str | None) -> dict:
        if not metadata.userinfo_endpoint or not access_token:
            raise SsoError("failed", "The provider gave no email and has no userinfo endpoint.")
        try:
            response = self.http.get(
                metadata.userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            response.raise_for_status()
            info = response.json()
        except (httpx2.HTTPError, ValueError) as error:
            raise SsoError("failed", f"Userinfo request failed: {error}") from error
        if not isinstance(info, dict):
            raise SsoError("failed", "Unexpected userinfo response.")
        return info

    def identity(self, code: str, verifier: str, redirect_uri: str, nonce: str) -> Identity:
        """Redeem the authorization code and return who the provider says signed in."""
        metadata = self.metadata()
        tokens = self._exchange(metadata, code, verifier, redirect_uri)
        claims = self._verify_id_token(metadata, tokens["id_token"], nonce)
        if "email" not in claims:
            # Many providers put profile claims only in the userinfo response.
            info = self._userinfo(metadata, tokens.get("access_token"))
            if info.get("sub") != claims["sub"]:
                raise SsoError("failed", "Userinfo belongs to another subject.")
            claims = {**info, **claims}
        email = claims.get("email")
        if not isinstance(email, str) or not email:
            raise SsoError("failed", "The provider did not share an email address.")
        return Identity(email=email, email_verified=_is_true(claims.get("email_verified")))
