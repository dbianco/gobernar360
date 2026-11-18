"""Password hashing and session tokens."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerificationError, InvalidHashError):
        return False


# Verified against when the email is unknown, so both failures take similar time.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session_token() -> tuple[str, str]:
    """Return (token for the cookie, hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, hash_session_token(token)


def normalize_email(raw: str) -> str:
    return raw.strip().lower()
