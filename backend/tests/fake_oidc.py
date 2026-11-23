"""An OpenID Connect provider for tests, served through an httpx2 mock transport.

It does what a real one checks: client credentials, redirect URI, single-use codes and
the PKCE verifier against the challenge of the authorization request.
"""

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import httpx2
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

ISSUER = "https://idp.test"
CLIENT_ID = "gobernar360"
CLIENT_SECRET = "test-client-secret"


def _new_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@dataclass
class Grant:
    email: str
    verified: bool
    nonce: str
    challenge: str
    redirect_uri: str


@dataclass
class FakeProvider:
    key: rsa.RSAPrivateKey = field(default_factory=_new_key)
    kid: str = "key-1"
    # Put the email in the ID token, or only in the userinfo response.
    email_in_id_token: bool = True
    # Claims to overwrite in the next ID tokens, e.g. a wrong nonce or audience.
    id_token_overrides: dict = field(default_factory=dict)
    # Sign with this key instead of the published one.
    signing_key: rsa.RSAPrivateKey | None = None
    grants: dict[str, Grant] = field(default_factory=dict)
    token_requests: list[httpx2.Request] = field(default_factory=list)
    access_tokens: dict[str, Grant] = field(default_factory=dict)

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self.handle)

    def authorize(self, authorization_url: str, email: str, verified: bool = True) -> dict:
        """What the provider does when the person signs in: returns the callback query."""
        url = urlparse(authorization_url)
        assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISSUER}/authorize"
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        assert query["client_id"] == CLIENT_ID
        assert query["response_type"] == "code"
        assert query["code_challenge_method"] == "S256"
        assert "openid" in query["scope"].split()
        code = secrets.token_urlsafe(16)
        self.grants[code] = Grant(
            email=email,
            verified=verified,
            nonce=query["nonce"],
            challenge=query["code_challenge"],
            redirect_uri=query["redirect_uri"],
        )
        return {"code": code, "state": query["state"]}

    def _claims(self, grant: Grant) -> dict:
        return {"sub": f"sub-{grant.email}", "email": grant.email, "email_verified": grant.verified}

    def _id_token(self, grant: Grant) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "iat": now,
            "exp": now + 300,
            "nonce": grant.nonce,
            "sub": f"sub-{grant.email}",
        }
        if self.email_in_id_token:
            claims |= self._claims(grant)
        claims |= self.id_token_overrides
        return jwt.encode(
            claims, self.signing_key or self.key, algorithm="RS256", headers={"kid": self.kid}
        )

    def _json(self, body: object, status: int = 200) -> httpx2.Response:
        return httpx2.Response(status, json=body)

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return self._json(
                {
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                    "userinfo_endpoint": f"{ISSUER}/userinfo",
                    "token_endpoint_auth_methods_supported": ["client_secret_basic"],
                }
            )
        if path == "/jwks":
            public = RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
            return self._json({"keys": [public | {"kid": self.kid, "use": "sig"}]})
        if path == "/token":
            return self._token(request)
        if path == "/userinfo":
            token = request.headers.get("authorization", "").removeprefix("Bearer ")
            grant = self.access_tokens.get(token)
            if grant is None:
                return self._json({"error": "invalid_token"}, 401)
            return self._json(self._claims(grant))
        return self._json({"error": "not_found"}, 404)

    def _token(self, request: httpx2.Request) -> httpx2.Response:
        self.token_requests.append(request)
        expected = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        if request.headers.get("authorization") != f"Basic {expected}":
            return self._json({"error": "invalid_client"}, 401)
        form = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        grant = self.grants.pop(form.get("code", ""), None)
        if grant is None or form.get("grant_type") != "authorization_code":
            return self._json({"error": "invalid_grant"}, 400)
        if form.get("redirect_uri") != grant.redirect_uri:
            return self._json({"error": "invalid_grant"}, 400)
        digest = hashlib.sha256(form.get("code_verifier", "").encode()).digest()
        if base64.urlsafe_b64encode(digest).rstrip(b"=").decode() != grant.challenge:
            return self._json({"error": "invalid_grant", "error_description": "PKCE"}, 400)
        access_token = secrets.token_urlsafe(16)
        self.access_tokens[access_token] = grant
        return httpx2.Response(
            200,
            content=json.dumps(
                {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": 300,
                    "id_token": self._id_token(grant),
                }
            ),
            headers={"content-type": "application/json"},
        )
