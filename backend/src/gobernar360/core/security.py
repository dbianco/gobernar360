"""Password hashing and secret tokens."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


# Verified against when the email is unknown or the account has no password yet,
# so every failure takes similar time.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def verify_password(plain: str, hashed: str | None) -> bool:
    """False for an account without a password, after spending the same time."""
    try:
        return _hasher.verify(hashed or DUMMY_PASSWORD_HASH, plain) and hashed is not None
    except (VerificationError, InvalidHashError):
        return False


def hash_token(token: str) -> str:
    """What is stored for a session cookie or a link token: never the token itself."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> tuple[str, str]:
    """Return (token to hand out, hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def normalize_email(raw: str) -> str:
    return raw.strip().lower()
