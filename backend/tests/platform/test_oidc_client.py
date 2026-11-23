"""The OpenID Connect client on its own: what it asks the provider, what it accepts back,
and the reason it gives (in the server log) for every sign-in it stops."""

import base64
import time
from urllib.parse import parse_qs, urlparse

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from gobernar360.core.config import get_settings
from gobernar360.platform import sso
from gobernar360.platform.sso import OidcClient, ProviderMetadata, SsoError
from tests.fake_oidc import CLIENT_ID, CLIENT_SECRET, ISSUER, _new_key

KEY = _new_key()
OTHER_KEY = _new_key()
NONCE = "the-nonce"
DISCOVERY_URL = f"{ISSUER}/.well-known/openid-configuration"


def _discovery(**changes) -> dict:
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/jwks",
        "userinfo_endpoint": f"{ISSUER}/userinfo",
        "token_endpoint_auth_methods_supported": ["client_secret_basic"],
    } | changes


def _jwk(key=KEY, kid: str | None = "key-1") -> dict:
    public = RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    return public | ({"kid": kid} if kid else {})


def _id_token(key=KEY, kid: str | None = "key-1", algorithm="RS256", **claims) -> str:
    now = int(time.time())
    body = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "iat": now,
        "exp": now + 300,
        "sub": "sub-ana",
        "nonce": NONCE,
        "email": "ana@noetinger.test",
        "email_verified": True,
    } | claims
    body = {name: value for name, value in body.items() if value is not None}
    headers = {"kid": kid} if kid else {}
    return jwt.encode(body, key, algorithm=algorithm, headers=headers)


class Provider:
    """Answers each path with what the test put in `routes`, and records every request."""

    def __init__(self, **routes) -> None:
        self.routes = {
            "/.well-known/openid-configuration": _discovery(),
            "/jwks": {"keys": [_jwk()]},
            "/token": {"access_token": "at-1", "id_token": _id_token()},
            "/userinfo": {"sub": "sub-ana", "email": "ana@noetinger.test"},
        } | routes
        self.requests: list[httpx2.Request] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        answer = self.routes.get(request.url.path)
        if callable(answer):
            answer = answer(request)
        if isinstance(answer, httpx2.Response):
            return answer
        if answer is None:
            return httpx2.Response(404, json={"error": "not_found"})
        return httpx2.Response(200, json=answer)

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


@pytest.fixture(autouse=True)
def fresh_cache():
    sso.clear_cache()
    yield
    sso.clear_cache()


def _client(provider: Provider, **settings) -> OidcClient:
    values = {
        "oidc_issuer": ISSUER + "/",
        "oidc_client_id": CLIENT_ID,
        "oidc_client_secret": CLIENT_SECRET,
    } | settings
    http = httpx2.Client(transport=httpx2.MockTransport(provider.handle))
    return OidcClient(get_settings().model_copy(update=values), http)


def _fails(call, detail: str, code: str = "failed") -> SsoError:
    with pytest.raises(SsoError) as raised:
        call()
    assert raised.value.code == code
    assert detail in str(raised.value)
    return raised.value


# Protocol helpers


def test_the_pkce_challenge_is_the_s256_of_the_verifier():
    # The example of RFC 7636, appendix B.
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert sso.pkce_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_an_error_without_detail_reads_as_its_code():
    assert str(SsoError("disabled")) == "disabled"
    assert str(SsoError("failed", "Token request failed")) == "Token request failed"


def test_the_http_client_does_not_follow_redirects_and_gives_up_in_ten_seconds():
    dependency = sso.get_http_client()
    http = next(dependency)
    assert http.follow_redirects is False
    assert http.timeout.read == 10
    dependency.close()


# Discovery


def test_discovery_is_read_once_and_kept_for_ten_minutes(monkeypatch):
    provider = Provider()
    client = _client(provider)
    now = [1000.0]
    monkeypatch.setattr(sso.time, "monotonic", lambda: now[0])

    first = client.metadata()
    now[0] += sso.CACHE_SECONDS - 1
    client.metadata()
    assert provider.paths() == ["/.well-known/openid-configuration"]
    now[0] += 1
    client.metadata()

    assert provider.paths() == ["/.well-known/openid-configuration"] * 2
    assert provider.requests[0].headers["accept"] == "application/json"
    assert first == ProviderMetadata(
        issuer=ISSUER,
        authorization_endpoint=f"{ISSUER}/authorize",
        token_endpoint=f"{ISSUER}/token",
        jwks_uri=f"{ISSUER}/jwks",
        userinfo_endpoint=f"{ISSUER}/userinfo",
        token_auth_methods=("client_secret_basic",),
    )


def test_discovery_defaults_to_basic_client_authentication_and_no_userinfo():
    document = _discovery()
    del document["token_endpoint_auth_methods_supported"]
    del document["userinfo_endpoint"]

    metadata = _client(Provider(**{"/.well-known/openid-configuration": document})).metadata()

    assert metadata.token_auth_methods == ("client_secret_basic",)
    assert metadata.userinfo_endpoint is None


def test_discovery_accepts_the_issuer_with_a_trailing_slash():
    provider = Provider(**{"/.well-known/openid-configuration": _discovery(issuer=ISSUER + "/")})
    assert _client(provider).metadata().issuer == ISSUER + "/"


@pytest.mark.parametrize(
    ("answer", "detail"),
    [
        (httpx2.Response(500, text="down"), f"Could not read {DISCOVERY_URL}: "),
        (httpx2.Response(200, text="<html>"), f"Could not read {DISCOVERY_URL}: "),
        ({"issuer": ISSUER}, "Incomplete discovery document: 'authorization_endpoint'"),
        ([], "Incomplete discovery document: "),
        (_discovery(issuer="https://evil.test"), "Discovery names issuer https://evil.test"),
    ],
)
def test_a_discovery_document_that_cannot_be_used_stops_the_sign_in(answer, detail):
    client = _client(Provider(**{"/.well-known/openid-configuration": answer}))
    _fails(client.metadata, detail)


def test_a_failed_read_is_not_kept():
    provider = Provider(**{"/.well-known/openid-configuration": httpx2.Response(503)})
    client = _client(provider)
    _fails(client.metadata, "Could not read")

    provider.routes["/.well-known/openid-configuration"] = _discovery()

    assert client.metadata().issuer == ISSUER


# Authorization request


def test_the_authorization_url_carries_the_whole_request():
    client = _client(Provider(), oidc_scopes="openid email")

    url = urlparse(
        client.authorization_url("st-1", "no-1", "verifier-1", "https://app.test/callback")
    )

    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISSUER}/authorize"
    assert parse_qs(url.query) == {
        "response_type": ["code"],
        "client_id": [CLIENT_ID],
        "redirect_uri": ["https://app.test/callback"],
        "scope": ["openid email"],
        "state": ["st-1"],
        "nonce": ["no-1"],
        "code_challenge": [sso.pkce_challenge("verifier-1")],
        "code_challenge_method": ["S256"],
    }


def test_the_authorization_url_keeps_a_query_the_endpoint_already_has():
    discovery = _discovery(authorization_endpoint=f"{ISSUER}/authorize?tenant=muni")
    client = _client(Provider(**{"/.well-known/openid-configuration": discovery}))

    url = client.authorization_url("st-1", "no-1", "verifier-1", "https://app.test/cb")

    assert url.startswith(f"{ISSUER}/authorize?tenant=muni&response_type=code&")


# Token request


def _form(request: httpx2.Request) -> dict:
    return {key: values[0] for key, values in parse_qs(request.content.decode()).items()}


def _token_request(provider: Provider) -> httpx2.Request:
    return next(request for request in provider.requests if request.url.path == "/token")


def test_the_code_is_redeemed_with_basic_authentication_form_encoded():
    provider = Provider()
    client = _client(provider, oidc_client_id="muni app", oidc_client_secret="s3cr:t&+")

    tokens = client._exchange(client.metadata(), "code-1", "verifier-1", "https://app.test/cb")

    request = _token_request(provider)
    assert tokens["access_token"] == "at-1"
    assert request.method == "POST"
    assert request.headers["accept"] == "application/json"
    credentials = base64.b64decode(request.headers["authorization"].removeprefix("Basic "))
    assert credentials.decode() == "muni+app:s3cr%3At%26%2B"
    assert _form(request) == {
        "grant_type": "authorization_code",
        "code": "code-1",
        "redirect_uri": "https://app.test/cb",
        "code_verifier": "verifier-1",
    }


def test_the_secret_goes_in_the_form_when_the_provider_does_not_take_basic():
    discovery = _discovery(token_endpoint_auth_methods_supported=["client_secret_post"])
    provider = Provider(**{"/.well-known/openid-configuration": discovery})
    client = _client(provider)

    client._exchange(client.metadata(), "code-1", "verifier-1", "https://app.test/cb")

    request = _token_request(provider)
    assert "authorization" not in request.headers
    assert _form(request) == {
        "grant_type": "authorization_code",
        "code": "code-1",
        "redirect_uri": "https://app.test/cb",
        "code_verifier": "verifier-1",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }


def test_a_public_client_sends_only_its_id():
    provider = Provider()
    client = _client(provider, oidc_client_secret="")

    client._exchange(client.metadata(), "code-1", "verifier-1", "https://app.test/cb")

    request = _token_request(provider)
    assert "authorization" not in request.headers
    assert _form(request)["client_id"] == CLIENT_ID
    assert "client_secret" not in _form(request)


@pytest.mark.parametrize(
    ("answer", "detail"),
    [
        (httpx2.Response(400, json={"error": "invalid_grant"}), "Token request failed: "),
        (httpx2.Response(200, text="nope"), "Token request failed: "),
        (["id_token"], "The token response has no ID token."),
        ({"access_token": "at-1"}, "The token response has no ID token."),
        ({"access_token": "at-1", "id_token": ""}, "The token response has no ID token."),
    ],
)
def test_a_token_response_that_cannot_be_used_stops_the_sign_in(answer, detail):
    client = _client(Provider(**{"/token": answer}))
    metadata = client.metadata()
    _fails(lambda: client._exchange(metadata, "code-1", "v", "https://app.test/cb"), detail)


# ID token


def _verify(provider: Provider, token: str, nonce: str = NONCE, **settings) -> dict:
    client = _client(provider, **settings)
    return client._verify_id_token(client.metadata(), token, nonce)


def test_a_valid_id_token_gives_its_claims():
    claims = _verify(Provider(), _id_token())
    assert (claims["sub"], claims["email"]) == ("sub-ana", "ana@noetinger.test")


def test_an_id_token_for_several_audiences_must_name_this_client_as_authorized_party():
    token = _id_token(aud=[CLIENT_ID, "other-app"], azp=CLIENT_ID)
    assert _verify(Provider(), token)["azp"] == CLIENT_ID

    _fails(
        lambda: _verify(Provider(), _id_token(aud=[CLIENT_ID, "other-app"], azp="other-app")),
        "ID token issued to another party.",
    )
    _fails(
        lambda: _verify(Provider(), _id_token(aud=[CLIENT_ID, "other-app"])),
        "ID token issued to another party.",
    )


def test_a_single_audience_in_a_list_needs_no_authorized_party():
    assert _verify(Provider(), _id_token(aud=[CLIENT_ID]))["aud"] == [CLIENT_ID]


def test_the_nonce_must_be_the_one_of_this_sign_in():
    _fails(
        lambda: _verify(Provider(), _id_token(), nonce="another"),
        "ID token nonce does not match this sign-in.",
    )
    # A token without nonce never matches a sign-in, which always sends one.
    _fails(
        lambda: _verify(Provider(), _id_token(nonce=None)),
        "ID token nonce does not match this sign-in.",
    )


def test_a_malformed_id_token_stops_the_sign_in():
    _fails(lambda: _verify(Provider(), "not-a-token"), "Malformed ID token: ")


def test_an_id_token_signed_with_a_shared_secret_is_refused():
    token = jwt.encode({"sub": "x"}, "a-secret-long-enough-for-hs256-0000", algorithm="HS256")
    _fails(lambda: _verify(Provider(), token), "ID token signed with HS256.")


def test_an_unsigned_id_token_is_refused():
    token = jwt.encode({"sub": "x"}, None, algorithm="none")
    _fails(lambda: _verify(Provider(), token), "ID token signed with none.")


@pytest.mark.parametrize(
    ("claims", "detail"),
    [
        ({"iss": "https://evil.test"}, "Invalid ID token: Invalid issuer"),
        ({"aud": "other-app"}, "Invalid ID token: Audience doesn't match"),
        ({"exp": int(time.time()) - 120}, "Invalid ID token: Signature has expired"),
        ({"sub": None}, 'Invalid ID token: Token is missing the "sub" claim'),
        ({"iat": None}, 'Invalid ID token: Token is missing the "iat" claim'),
    ],
)
def test_the_claims_of_the_id_token_are_checked(claims, detail):
    _fails(lambda: _verify(Provider(), _id_token(**claims)), detail)


def test_a_token_expired_within_a_minute_is_still_accepted():
    token = _id_token(exp=int(time.time()) - 30)
    assert _verify(Provider(), token)["sub"] == "sub-ana"


def test_an_id_token_whose_signature_does_not_match_the_key_is_refused():
    _fails(
        lambda: _verify(Provider(), _id_token(key=OTHER_KEY)),
        "Invalid ID token: Signature verification failed",
    )


def test_an_elliptic_curve_signature_is_accepted():
    key = ec.generate_private_key(ec.SECP256R1())
    public = ECAlgorithm.to_jwk(key.public_key(), as_dict=True) | {"kid": "ec-1"}
    provider = Provider(**{"/jwks": {"keys": [public]}})

    token = _id_token(key=key, kid="ec-1", algorithm="ES256")

    assert _verify(provider, token)["sub"] == "sub-ana"


# Signing keys


def test_a_token_without_key_id_uses_the_only_key_published():
    provider = Provider(**{"/jwks": {"keys": [_jwk(kid=None)]}})
    assert _verify(provider, _id_token(kid=None))["sub"] == "sub-ana"


def test_a_token_without_key_id_is_refused_when_several_keys_are_published():
    provider = Provider(**{"/jwks": {"keys": [_jwk(kid="a"), _jwk(OTHER_KEY, kid="b")]}})
    _fails(lambda: _verify(provider, _id_token(kid=None)), "No signing key None at the provider.")
    # It does not fetch the keys again: another copy would not tell which one to use.
    assert provider.paths().count("/jwks") == 1


def test_keys_are_fetched_again_for_an_unknown_key_id():
    provider = Provider(**{"/jwks": {"keys": [_jwk(kid="old")]}})
    client = _client(provider)
    metadata = client.metadata()
    client._signing_key(metadata, {"kid": "old", "alg": "RS256"}, cached=True)
    provider.routes["/jwks"] = {"keys": [_jwk(kid="old"), _jwk(OTHER_KEY, kid="new")]}

    token = _id_token(key=OTHER_KEY, kid="new")

    assert client._verify_id_token(metadata, token, NONCE)["sub"] == "sub-ana"
    assert provider.paths().count("/jwks") == 2


def test_a_key_id_the_provider_does_not_publish_stops_the_sign_in():
    provider = Provider()
    _fails(lambda: _verify(provider, _id_token(kid="gone")), "No signing key gone at the provider.")
    assert provider.paths().count("/jwks") == 2


def test_a_key_set_without_keys_has_no_signing_key():
    _fails(
        lambda: _verify(Provider(**{"/jwks": {}}), _id_token()),
        "No signing key key-1 at the provider.",
    )


def test_a_published_key_that_cannot_be_read_stops_the_sign_in():
    provider = Provider(**{"/jwks": {"keys": [{"kid": "key-1", "kty": "RSA", "n": "x"}]}})
    _fails(lambda: _verify(provider, _id_token()), "Unusable signing key: ")


def test_a_key_replaced_under_the_same_id_is_fetched_again_once():
    provider = Provider()
    client = _client(provider)
    metadata = client.metadata()
    client._verify_id_token(metadata, _id_token(), NONCE)
    provider.routes["/jwks"] = {"keys": [_jwk(OTHER_KEY)]}

    claims = client._verify_id_token(metadata, _id_token(key=OTHER_KEY), NONCE)

    assert claims["sub"] == "sub-ana"
    assert provider.paths().count("/jwks") == 2


def test_a_signature_wrong_with_fresh_keys_too_is_refused_after_one_retry():
    provider = Provider()
    client = _client(provider)
    metadata = client.metadata()
    client._verify_id_token(metadata, _id_token(), NONCE)

    _fails(
        lambda: client._verify_id_token(metadata, _id_token(key=OTHER_KEY), NONCE),
        "Invalid ID token: Signature verification failed",
    )
    assert provider.paths().count("/jwks") == 2


def test_keys_read_without_the_cache_are_kept_for_the_next_sign_in():
    provider = Provider()
    client = _client(provider)
    metadata = client.metadata()

    client._signing_key(metadata, {"kid": "key-1", "alg": "RS256"}, cached=False)
    client._signing_key(metadata, {"kid": "key-1", "alg": "RS256"}, cached=True)

    assert provider.paths().count("/jwks") == 1


# Userinfo and identity


def test_userinfo_is_asked_with_the_access_token():
    provider = Provider()
    client = _client(provider)

    info = client._userinfo(client.metadata(), "at-1")

    request = provider.requests[-1]
    assert request.url.path == "/userinfo"
    assert request.headers["authorization"] == "Bearer at-1"
    assert request.headers["accept"] == "application/json"
    assert info == {"sub": "sub-ana", "email": "ana@noetinger.test"}


@pytest.mark.parametrize(
    ("discovery", "access_token", "answer", "detail"),
    [
        (
            {"userinfo_endpoint": None},
            "at-1",
            None,
            "The provider gave no email and has no userinfo endpoint.",
        ),
        ({}, None, None, "The provider gave no email and has no userinfo endpoint."),
        ({}, "at-1", httpx2.Response(401), "Userinfo request failed: "),
        ({}, "at-1", httpx2.Response(200, text="x"), "Userinfo request failed: "),
        ({}, "at-1", ["sub-ana"], "Unexpected userinfo response."),
    ],
)
def test_userinfo_that_cannot_be_used_stops_the_sign_in(discovery, access_token, answer, detail):
    provider = Provider(
        **{"/.well-known/openid-configuration": _discovery(**discovery), "/userinfo": answer}
    )
    client = _client(provider)
    metadata = client.metadata()
    _fails(lambda: client._userinfo(metadata, access_token), detail)


def _identity(provider: Provider):
    return _client(provider).identity("code-1", "verifier-1", "https://app.test/cb", NONCE)


def test_the_identity_comes_from_the_id_token():
    assert _identity(Provider()) == sso.Identity("ana@noetinger.test", True)


@pytest.mark.parametrize(
    ("verified", "expected"),
    [(True, True), ("true", True), (False, False), ("false", False), ("yes", False), (1, False)],
)
def test_only_a_true_verification_claim_counts(verified, expected):
    provider = Provider(**{"/token": {"id_token": _id_token(email_verified=verified)}})
    assert _identity(provider).email_verified is expected


def test_a_missing_verification_claim_means_not_verified():
    provider = Provider(**{"/token": {"id_token": _id_token(email_verified=None)}})
    assert _identity(provider).email_verified is False


def test_the_email_comes_from_userinfo_when_the_id_token_lacks_it():
    token = _id_token(email=None, email_verified=None)
    provider = Provider(
        **{
            "/token": {"access_token": "at-1", "id_token": token},
            "/userinfo": {"sub": "sub-ana", "email": "ana@noetinger.test", "email_verified": True},
        }
    )

    assert _identity(provider) == sso.Identity("ana@noetinger.test", True)


def test_the_id_token_wins_over_userinfo_on_the_claims_both_have():
    token = _id_token(email=None, email_verified=False)
    provider = Provider(
        **{
            "/token": {"access_token": "at-1", "id_token": token},
            "/userinfo": {"sub": "sub-ana", "email": "ana@noetinger.test", "email_verified": True},
        }
    )

    assert _identity(provider).email_verified is False


def test_userinfo_about_another_subject_stops_the_sign_in():
    provider = Provider(
        **{
            "/token": {"access_token": "at-1", "id_token": _id_token(email=None)},
            "/userinfo": {"sub": "sub-eve", "email": "eve@evil.test"},
        }
    )
    _fails(lambda: _identity(provider), "Userinfo belongs to another subject.")


@pytest.mark.parametrize("email", [None, "", 42])
def test_a_sign_in_without_an_email_stops(email):
    provider = Provider(
        **{
            "/token": {"access_token": "at-1", "id_token": _id_token(email=None)},
            "/userinfo": {"sub": "sub-ana"} | ({} if email is None else {"email": email}),
        }
    )
    _fails(lambda: _identity(provider), "The provider did not share an email address.")


def test_the_identity_asks_for_discovery_token_and_keys_in_that_order():
    provider = Provider()
    _identity(provider)
    assert provider.paths() == ["/.well-known/openid-configuration", "/token", "/jwks"]


def test_the_token_request_is_sent_to_the_endpoint_discovery_names():
    discovery = _discovery(token_endpoint=f"{ISSUER}/oauth2/token")
    provider = Provider(
        **{
            "/.well-known/openid-configuration": discovery,
            "/oauth2/token": {"id_token": _id_token()},
            "/token": None,
        }
    )
    assert _identity(provider).email == "ana@noetinger.test"
    assert provider.paths()[1] == "/oauth2/token"
