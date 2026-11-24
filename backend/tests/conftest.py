"""Shared fixtures. The suite runs against the real gobernar360_test database."""

import os
from pathlib import Path

# Must be set before any gobernar360 module reads its settings.
os.environ["GOBERNAR360_DATABASE_URL"] = (
    "postgresql+psycopg://gobernar360_app:gobernar360_app@localhost:5434/gobernar360_test"
)
os.environ["GOBERNAR360_ADMIN_DATABASE_URL"] = (
    "postgresql+psycopg://gobernar360:gobernar360@localhost:5434/gobernar360_test"
)
os.environ["GOBERNAR360_PUBLIC_DATABASE_URL"] = (
    "postgresql+psycopg://gobernar360_public:gobernar360_public@localhost:5434/gobernar360_test"
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from gobernar360.core.db import Base, get_admin_engine  # noqa: E402
from gobernar360.main import create_app  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clean_database(migrated_database):
    from gobernar360.platform.public_router import limiter

    # The public routes count requests per address, and every test comes from the same one.
    limiter.reset()
    yield
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with get_admin_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    with TestClient(create_app(), headers={"X-Requested-With": "gobernar360"}) as test_client:
        yield test_client


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
