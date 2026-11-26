"""Secrets at rest, encrypted with the installation's key (GOBERNAR360_SECRETS_KEY)."""

import json

from cryptography.fernet import Fernet, InvalidToken

from gobernar360.core.config import get_settings


class SecretsUnavailable(Exception):
    """There is no usable key, or what is stored was not encrypted with it."""


def _fernet() -> Fernet:
    key = get_settings().secrets_key
    if not key:
        raise SecretsUnavailable("GOBERNAR360_SECRETS_KEY is not set.")
    try:
        return Fernet(key)
    except ValueError:
        # Without the cause: it may quote the key.
        raise SecretsUnavailable("GOBERNAR360_SECRETS_KEY is not a Fernet key.") from None


def is_available() -> bool:
    try:
        _fernet()
    except SecretsUnavailable:
        return False
    return True


def encrypt(value: str, owner: str) -> bytes:
    """`owner` says whose secret it is: `decrypt` refuses it for anybody else, so a value
    copied to another row is of no use there."""
    return _fernet().encrypt(json.dumps({"owner": owner, "value": value}).encode())


def decrypt(encrypted: bytes, owner: str) -> str:
    try:
        stored = json.loads(_fernet().decrypt(encrypted))
    except InvalidToken:
        raise SecretsUnavailable("The secret was encrypted with another key.") from None
    if stored["owner"] != owner:
        raise SecretsUnavailable("The secret belongs to somebody else.")
    return stored["value"]
