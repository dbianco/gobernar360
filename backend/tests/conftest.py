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
    yield
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with get_admin_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    with TestClient(create_app(), headers={"X-Requested-With": "gobernar360"}) as test_client:
        yield test_client
