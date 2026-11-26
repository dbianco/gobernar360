"""In production the API does not start with what is only for development."""

import pytest

from gobernar360 import main
from gobernar360.core.config import Settings, get_settings

DATABASE = "postgresql+psycopg://{}:{}@db:5432/gobernar360"
SAFE = {
    "database_url": DATABASE.format("gobernar360_app", "a-real-one"),
    "public_database_url": DATABASE.format("gobernar360_public", "another%40real"),
}
DEFAULT_APP = DATABASE.format("gobernar360_app", "gobernar360_app")
DEFAULT_PUBLIC = DATABASE.format("gobernar360_public", "gobernar360_public")


def _settings(**changes) -> Settings:
    return Settings(**(SAFE | changes))


def test_development_starts_with_the_passwords_of_development():
    settings = Settings()

    assert (settings.environment, settings.is_production) == ("development", False)
    main.check_production(_settings(database_url=DEFAULT_APP, public_database_url=DEFAULT_PUBLIC))


@pytest.mark.parametrize("production", [{"environment": "production"}, {"cookie_secure": True}])
@pytest.mark.parametrize(
    ("changes", "named"),
    [
        (
            {"public_database_url": DEFAULT_PUBLIC},
            "GOBERNAR360_PUBLIC_DATABASE_URL",
        ),
        ({"database_url": DEFAULT_APP}, "GOBERNAR360_DATABASE_URL"),
        (
            {"database_url": DEFAULT_APP, "public_database_url": DEFAULT_PUBLIC},
            "GOBERNAR360_DATABASE_URL and GOBERNAR360_PUBLIC_DATABASE_URL",
        ),
        # The same, written otherwise.
        (
            {"public_database_url": DATABASE.format("gobernar360_public", "gobernar360%5Fpublic")},
            "GOBERNAR360_PUBLIC_DATABASE_URL",
        ),
    ],
)
def test_production_does_not(production, changes, named):
    with pytest.raises(RuntimeError) as raised:
        main.check_production(_settings(**production, **changes))

    assert str(raised.value) == (
        f"{named} still use the password of the development database. Change it "
        "(ALTER ROLE ... PASSWORD ...) before serving anybody."
    )


@pytest.mark.parametrize(
    "changes",
    [
        {},
        # Without a password in the address it comes from elsewhere, e.g. a certificate.
        {"public_database_url": "postgresql+psycopg://gobernar360_public@db/gobernar360"},
    ],
)
def test_production_starts_with_its_own(changes):
    main.check_production(_settings(environment="production", **changes))


@pytest.mark.parametrize("production", [{"environment": "production"}, {"cookie_secure": True}])
def test_production_does_not_start_with_the_fake_cidi(production):
    with pytest.raises(RuntimeError) as raised:
        main.check_production(_settings(**production, cidi_mode="fake"))

    assert str(raised.value) == ("GOBERNAR360_CIDI_MODE is fake: residents would be told nothing.")
    for mode in ("off", "live"):
        main.check_production(_settings(**production, cidi_mode=mode))
    main.check_production(_settings(cidi_mode="fake"))


def test_the_app_is_not_built_at_all(monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")

    with pytest.raises(RuntimeError, match="password of the development database"):
        main.create_app()
