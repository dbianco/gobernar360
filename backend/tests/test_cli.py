"""The administration commands (`gobernar360 ...`)."""

from datetime import date

from sqlalchemy import select
from typer.testing import CliRunner

from gobernar360 import cli
from gobernar360.platform.models import User
from gobernar360.platform.snapshots import SnapshotReport
from tests.factories import admin_session, login, make_user

runner = CliRunner()


def create_operator(*args: str):
    return runner.invoke(cli.app, ["create-operator", *args])


def test_create_operator_adds_an_operator_who_can_sign_in(client):
    result = create_operator(
        "--email", " Ops@Gobernar360.test ", "--full-name", "Operadora", "--password",
        "long-password-1",
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert "Operator ops@gobernar360.test created." in result.output
    with admin_session() as session:
        operator = session.scalar(select(User).where(User.email == "ops@gobernar360.test"))
    assert operator.is_platform_operator
    me = login(client, "ops@gobernar360.test", "long-password-1").json()
    assert me["user"]["is_platform_operator"] is True


def test_create_operator_refuses_an_existing_email_and_a_short_password():
    make_user("ops@gobernar360.test")

    taken = create_operator(
        "--email", "ops@gobernar360.test", "--full-name", "X", "--password", "long-password-1"
    )
    short = create_operator(
        "--email", "new@gobernar360.test", "--full-name", "X", "--password", "short"
    )

    assert taken.exit_code == 2
    assert "already exists" in taken.output
    assert short.exit_code == 2
    assert "at least 10 characters" in short.output
    with admin_session() as session:
        assert session.scalar(select(User).where(User.email == "new@gobernar360.test")) is None


def test_seed_demo_says_whether_it_loaded_anything():
    first = runner.invoke(cli.app, ["seed-demo"])
    again = runner.invoke(cli.app, ["seed-demo"])

    assert first.exit_code == 0, first.output
    assert "Demo data loaded." in first.output
    assert "Demo data already present; nothing changed." in again.output


def test_the_snapshot_command_fails_when_a_municipality_could_not_be_snapshotted(monkeypatch):
    monkeypatch.setattr(cli, "get_today", lambda: date(2026, 4, 15))
    monkeypatch.setattr(
        "gobernar360.platform.snapshots.take_snapshots",
        lambda today, since: SnapshotReport(month=(2026, 4), municipalities=1, failed=["saira"]),
    )

    result = runner.invoke(cli.app, ["snapshot-indicators"])

    assert result.exit_code == 1
    assert "Failed, left unchanged: saira" in result.output
