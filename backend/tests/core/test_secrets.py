"""Secrets at rest: only readable with the key, and by whom they belong to."""

import pytest
from cryptography.fernet import Fernet

from gobernar360.core import secrets
from gobernar360.core.config import get_settings
from gobernar360.core.secrets import SecretsUnavailable


@pytest.fixture
def key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(get_settings(), "secrets_key", key)
    return key


def test_a_secret_comes_back_for_its_owner(key):
    stored = secrets.encrypt("clave súper secreta", "m-1:api_key")

    assert secrets.decrypt(stored, "m-1:api_key") == "clave súper secreta"
    assert b"secreta" not in stored and b"m-1" not in stored


def test_the_same_secret_is_never_stored_the_same_way(key):
    assert secrets.encrypt("x", "m-1:a") != secrets.encrypt("x", "m-1:a")


def test_nobody_else_can_use_it(key):
    stored = secrets.encrypt("x", "m-1:api_key")

    for other in ("m-2:api_key", "m-1:token"):
        with pytest.raises(SecretsUnavailable, match="^The secret belongs to somebody else.$"):
            secrets.decrypt(stored, other)


def test_with_another_key_it_cannot_be_read(key, monkeypatch):
    stored = secrets.encrypt("x", "m-1:api_key")
    monkeypatch.setattr(get_settings(), "secrets_key", Fernet.generate_key().decode())

    with pytest.raises(SecretsUnavailable, match="^The secret was encrypted with another key.$"):
        secrets.decrypt(stored, "m-1:api_key")


def test_without_a_key_there_are_no_secrets():
    assert get_settings().secrets_key == ""
    assert secrets.is_available() is False
    with pytest.raises(SecretsUnavailable, match="^GOBERNAR360_SECRETS_KEY is not set.$"):
        secrets.encrypt("x", "m-1:a")


@pytest.mark.parametrize("bad", ["short", "not base64 at all, by any means", "ñ" * 44])
def test_a_key_that_is_not_one_is_not_quoted(monkeypatch, bad):
    monkeypatch.setattr(get_settings(), "secrets_key", bad)

    assert secrets.is_available() is False
    with pytest.raises(SecretsUnavailable) as raised:
        secrets.encrypt("x", "m-1:a")
    assert str(raised.value) == "GOBERNAR360_SECRETS_KEY is not a Fernet key."
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


def test_a_good_key_is_available(key):
    assert secrets.is_available() is True
