"""Runtime settings, read from GOBERNAR360_* environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOBERNAR360_", env_file=".env", extra="ignore")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
