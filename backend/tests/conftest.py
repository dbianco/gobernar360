"""Shared fixtures. The suite runs against a real database, normally gobernar360_test."""

import os
from pathlib import Path

import psycopg

SERVER = "localhost:5434"


def _test_database() -> str:
    """The database this test process uses.

    Normally gobernar360_test. With GOBERNAR360_TEST_DATABASES=N (mutation testing runs
    several test processes at once), each process takes the first free database of
    gobernar360_test_0 ... gobernar360_test_{N-1}, holding a lock on it until it exits,
    so no two processes ever share one. tests/make_test_databases.py creates them.
    """
    pool = int(os.environ.get("GOBERNAR360_TEST_DATABASES", "0"))
    if pool == 0:
        return "gobernar360_test"
    lock = psycopg.connect(
        f"postgresql://gobernar360:gobernar360@{SERVER}/gobernar360", autocommit=True
    )
    for index in range(pool):
        if lock.execute("SELECT pg_try_advisory_lock(360360, %s)", (index,)).fetchone()[0]:
            # Kept open on purpose: the lock lasts as long as this process.
            globals()["_pool_lock"] = lock
            return f"gobernar360_test_{index}"
    raise RuntimeError(f"All {pool} test databases are in use.")


def _point_settings_at(database: str) -> None:
    os.environ["GOBERNAR360_DATABASE_URL"] = (
        f"postgresql+psycopg://gobernar360_app:gobernar360_app@{SERVER}/{database}"
    )
    os.environ["GOBERNAR360_ADMIN_DATABASE_URL"] = (
        f"postgresql+psycopg://gobernar360:gobernar360@{SERVER}/{database}"
    )
    os.environ["GOBERNAR360_PUBLIC_DATABASE_URL"] = (
        f"postgresql+psycopg://gobernar360_public:gobernar360_public@{SERVER}/{database}"
    )


# Must be set before any gobernar360 module reads its settings.
_chosen = {"pid": os.getpid(), "database": _test_database()}
_point_settings_at(_chosen["database"])

from gobernar360.core.config import Settings  # noqa: E402

# A developer's backend/.env (see .env.example) must not change what the tests see.
Settings.model_config["env_file"] = None

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from gobernar360.core import security  # noqa: E402
from gobernar360.core.config import get_settings  # noqa: E402
from gobernar360.core.db import Base, get_admin_engine, get_engine  # noqa: E402
from gobernar360.main import create_app  # noqa: E402

# Production-strength hashing is slow on purpose; tests only need it to be argon2.
security._hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
security.DUMMY_PASSWORD_HASH = security.hash_password("not-a-real-password")

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _own_database_after_fork() -> None:
    """A process forked after this module loaded (mutmut runs each mutant that way) got
    its parent's database and open connections. Take a database of its own instead."""
    if os.getpid() == _chosen["pid"] or "GOBERNAR360_TEST_DATABASES" not in os.environ:
        return
    _chosen.update(pid=os.getpid(), database=_test_database())
    _point_settings_at(_chosen["database"])
    get_settings.cache_clear()
    for engine_factory in (get_engine, get_admin_engine):
        if engine_factory.cache_info().currsize:
            # The connections belong to the parent: forget them without closing them.
            engine_factory().dispose(close=False)
        engine_factory.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    _own_database_after_fork()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_database(migrated_database):
    from gobernar360.platform.public_router import limiter

    # The public routes count requests per address, and every test comes from the same one.
    limiter.reset()
    yield
    # DELETE is much faster than TRUNCATE on the few rows a test leaves behind.
    # Children first, so foreign keys never stop a delete.
    with get_admin_engine().begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(text(f'DELETE FROM "{table.name}"'))


@pytest.fixture(scope="session")
def app():
    """One application for the whole run: building it takes longer than most tests."""
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app, headers={"X-Requested-With": "gobernar360"}) as test_client:
        yield test_client
    # What a test put in place of a dependency must not reach the next one.
    app.dependency_overrides.clear()


DEMO_STATE = 7


def demo_summary(ctx, as_of):
    """The demo dashboard's indicators: the day of the month it is asked about, which it can
    tell for any past date, and a fixed value it only knows as of today."""
    from gobernar360.dashboards.registry import SummaryIndicator

    return [SummaryIndicator("demo.day", as_of.day), SummaryIndicator("demo.state", DEMO_STATE)]


@pytest.fixture
def demo_dashboard():
    """Registers a dashboard module under the key 'demo', known only to the tests.

    It has no routes of its own, but declares two indicators (see `demo_summary`).
    """
    from fastapi import APIRouter

    from gobernar360.dashboards import registry
    from gobernar360.dashboards.registry import DashboardModule, IndicatorDefinition

    registry.register(
        DashboardModule(
            key="demo",
            router=APIRouter(),
            get_summary=demo_summary,
            indicators=(
                IndicatorDefinition("demo.day", reconstructible=True, aggregate=True),
                # Not aggregate: it can never be published.
                IndicatorDefinition("demo.state", higher_is_better=False),
            ),
        )
    )
    yield "demo"
    registry.unregister("demo")
