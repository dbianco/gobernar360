"""Runtime settings, read from GOBERNAR360_* environment variables."""

from functools import lru_cache
from typing import Literal
from urllib.parse import unquote, urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


def _has_known_password(database_url: str) -> bool:
    """db/init and the migrations give each role its own name as its password."""
    parts = urlsplit(database_url)
    return parts.password is not None and unquote(parts.password) == parts.username


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOBERNAR360_", env_file=".env", extra="ignore")

    # "production" makes the API refuse to start with what is only safe in development.
    environment: Literal["development", "production"] = "development"

    # The API connects as a role that owns no tables, so row-level security applies to it.
    database_url: str = (
        "postgresql+psycopg://gobernar360_app:gobernar360_app@localhost:5434/gobernar360"
    )
    # Owner role, used only for migrations.
    admin_database_url: str = (
        "postgresql+psycopg://gobernar360:gobernar360@localhost:5434/gobernar360"
    )
    # The public transparency page connects as a role that can only read the published
    # copies, never tenant or account data.
    public_database_url: str = (
        "postgresql+psycopg://gobernar360_public:gobernar360_public@localhost:5434/gobernar360"
    )
    # Requests per minute and client address to the public routes.
    public_rate_limit_per_minute: int = 120
    session_ttl_hours: int = 12
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]

    # Address of the web app as people open it: links in emails and the single sign-on
    # callback are built from it.
    app_url: str = "http://localhost:5173"

    # Outgoing email. The defaults point at the local mail catcher of docker-compose.yml.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    # "starttls" upgrades a plain connection (usually port 587); "tls" is implicit TLS (465).
    smtp_security: Literal["none", "starttls", "tls"] = "none"
    smtp_timeout_seconds: float = 10
    email_from: str = "gobernar360 <no-reply@gobernar360.test>"

    invitation_ttl_hours: int = 7 * 24
    password_reset_ttl_minutes: int = 60
    # Password recovery requests accepted per email address within the window.
    password_reset_limit: int = 3
    password_reset_window_minutes: int = 60

    # Single sign-on through an OpenID Connect provider. Empty issuer: disabled.
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_scopes: str = "openid email profile"

    # CiDi, the provincial account (platform/cidi): whether notices to residents can go out
    # through it. "fake" writes them to a file instead; "live" waits for the Province.
    cidi_mode: Literal["off", "fake", "live"] = "off"
    cidi_fake_inbox: str = "./cidi-fake-inbox.jsonl"

    # Fernet key that encrypts the secrets municipalities save. Without it none is accepted.
    secrets_key: str = ""

    @property
    def is_production(self) -> bool:
        """Secure cookies are only on behind HTTPS, which is where people work."""
        return self.environment == "production" or self.cookie_secure

    def known_passwords(self) -> list[str]:
        """Database settings the API connects with that still have the password the
        repository gives their role, which anybody can read."""
        return [
            f"GOBERNAR360_{name.upper()}"
            for name in ("database_url", "public_database_url")
            if _has_known_password(getattr(self, name))
        ]

    @property
    def sso_enabled(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_client_id)

    def app_link(self, path: str) -> str:
        return self.app_url.rstrip("/") + path


@lru_cache
def get_settings() -> Settings:
    return Settings()
