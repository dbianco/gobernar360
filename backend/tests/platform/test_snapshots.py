"""Monthly snapshots of headline indicators (`platform/snapshots.py`, `snapshot-indicators`)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from gobernar360 import cli
from gobernar360.core.db import tenant_session
from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import DashboardModule, IndicatorDefinition
from gobernar360.main import register_dashboards
from gobernar360.platform.clock import get_today
from gobernar360.platform.models import IndicatorSnapshot
from gobernar360.platform.snapshots import take_snapshots
from tests.conftest import DEMO_STATE
from tests.economic.factories import (
    economic_member,
    make_actor,
    make_assignment,
    make_tool,
)
from tests.factories import admin_session, enable_dashboards, login, make_municipality

ECONOMIC = "/api/dashboards/economic"


@pytest.fixture(autouse=True)
def installed():
    # The command runs without the application, so it installs the dashboards itself.
    register_dashboards()


def rows(municipality=None) -> list[tuple]:
    """Every snapshot row, read through the owner connection, in a stable order."""
    query = select(IndicatorSnapshot).order_by(
        IndicatorSnapshot.municipality_id,
        IndicatorSnapshot.indicator_key,
        IndicatorSnapshot.year,
        IndicatorSnapshot.month,
    )
    if municipality is not None:
        query = query.where(IndicatorSnapshot.municipality_id == municipality.id)
    with admin_session() as session:
        return [
            (
                row.id,
                row.municipality_id,
                row.dashboard_key,
                row.indicator_key,
                row.year,
                row.month,
                row.value,
                row.taken_at,
            )
            for row in session.scalars(query)
        ]


def values(municipality, key: str) -> dict[tuple[int, int], Decimal | None]:
    return {(r[4], r[5]): r[6] for r in rows(municipality) if r[3] == key}


def economic_data(municipality, assignment_dates, actors=2):
    tool = make_tool(municipality)
    recipients = [make_actor(municipality, f"Actor {n}") for n in range(actors)]
    for day in assignment_dates:
        make_assignment(municipality, tool, actor=recipients[0], on=day)


def test_running_the_snapshot_twice_gives_the_same_rows():
    municipality = economic_member("viewer")
    economic_data(municipality, [date(2026, 1, 10), date(2026, 3, 2)])

    take_snapshots(date(2026, 4, 15), since=(2026, 1))
    first = rows()
    report = take_snapshots(date(2026, 4, 15), since=(2026, 1))

    assert rows() == first
    assert report.changed_rows == 0
    # This month with every indicator, and the three closed months of the one that can
    # be rebuilt.
    assert len(first) == 4 + 3


def test_a_rebuilt_month_matches_what_the_api_said_that_day(client):
    municipality = economic_member("viewer")
    economic_data(municipality, [date(2026, 1, 10), date(2026, 3, 2), date(2026, 3, 20)])
    login(client, "ana@noetinger.test")
    client.app.dependency_overrides[get_today] = lambda: date(2026, 3, 31)
    overview = client.get("/api/overview").json()[0]["indicators"]
    said_then = {indicator["key"]: indicator["value"] for indicator in overview}
    # Life goes on: more assignments after the month closed.
    economic_data(municipality, [date(2026, 4, 2), date(2026, 5, 6)])

    take_snapshots(date(2026, 5, 10), since=(2026, 1))

    rebuilt = values(municipality, "economic.assignments_year")
    assert said_then["economic.assignments_year"] == 3
    assert rebuilt[(2026, 3)] == said_then["economic.assignments_year"]
    assert rebuilt[(2026, 1)] == 1
    assert rebuilt[(2026, 4)] == 4
    # This month, as of today.
    assert rebuilt[(2026, 5)] == 5


def test_a_rebuilt_year_to_date_count_starts_again_in_january():
    municipality = economic_member("viewer")
    economic_data(municipality, [date(2025, 11, 3), date(2025, 12, 20), date(2026, 1, 5)])

    take_snapshots(date(2026, 2, 1), since=(2025, 11))

    assert values(municipality, "economic.assignments_year") == {
        (2025, 11): 1,
        (2025, 12): 2,
        (2026, 1): 1,
        # So far this year, as of today.
        (2026, 2): 1,
    }


def test_an_indicator_that_cannot_be_rebuilt_stays_empty_in_past_months():
    municipality = economic_member("viewer")
    economic_data(municipality, [date(2026, 1, 10)], actors=3)

    take_snapshots(date(2026, 4, 15), since=(2026, 1))

    # Only today is known: the actors loaded in January are not.
    assert values(municipality, "economic.actors") == {(2026, 4): 3}


def test_rebuilding_keeps_what_was_recorded_at_the_time():
    municipality = economic_member("viewer")
    economic_data(municipality, [date(2026, 1, 10)], actors=3)
    # The January run, when the municipality had a single actor.
    take_snapshots(date(2026, 1, 31))
    with admin_session() as session, session.begin():
        january = session.scalar(
            select(IndicatorSnapshot).where(IndicatorSnapshot.indicator_key == "economic.actors")
        )
        january.value = 1

    take_snapshots(date(2026, 4, 15), since=(2026, 1))

    assert values(municipality, "economic.actors") == {(2026, 1): 1, (2026, 4): 3}


def test_a_municipality_never_gets_snapshot_rows_of_another(client):
    noetinger = economic_member("viewer")
    economic_data(noetinger, [date(2026, 3, 2)], actors=2)
    saira = economic_member("viewer", "luis@saira.test", municipality_name="Saira")
    economic_data(saira, [date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5)], actors=5)

    take_snapshots(date(2026, 4, 15), since=(2026, 1))

    assert values(noetinger, "economic.actors") == {(2026, 4): 2}
    assert values(saira, "economic.actors") == {(2026, 4): 5}
    assert values(noetinger, "economic.assignments_year")[(2026, 3)] == 1
    assert values(saira, "economic.assignments_year")[(2026, 3)] == 3
    with tenant_session(noetinger.id) as db:
        seen = set(db.scalars(select(IndicatorSnapshot.municipality_id)))
    assert seen == {noetinger.id}
    # And through the API, each sees only its own history.
    login(client, "luis@saira.test")
    client.app.dependency_overrides[get_today] = lambda: date(2026, 4, 20)
    evolution = {i["key"]: i for i in client.get(f"{ECONOMIC}/evolution").json()}
    assert evolution["economic.assignments_year"]["previous_value"] == 3


def test_a_dashboard_known_only_to_the_tests_gets_snapshots(demo_dashboard):
    municipality = make_municipality("Noetinger")
    enable_dashboards(municipality, [demo_dashboard])

    take_snapshots(date(2026, 3, 10), since=(2026, 1))

    assert values(municipality, "demo.day") == {(2026, 1): 31, (2026, 2): 28, (2026, 3): 10}
    assert values(municipality, "demo.state") == {(2026, 3): DEMO_STATE}
    assert {row[2] for row in rows(municipality)} == {"demo"}


def test_disabled_dashboards_are_not_snapshotted(demo_dashboard):
    municipality = economic_member("viewer")
    economic_data(municipality, [date(2026, 3, 2)])

    take_snapshots(date(2026, 3, 10))

    assert {row[2] for row in rows(municipality)} == {"economic"}


def test_the_current_month_follows_the_data_until_it_closes():
    municipality = economic_member("viewer")
    economic_data(municipality, [date(2026, 3, 2)])
    take_snapshots(date(2026, 3, 10))
    tool, actor = make_tool(municipality, name="Curso"), make_actor(municipality, "Kiosco")
    make_assignment(municipality, tool, actor=actor, on=date(2026, 3, 12))

    take_snapshots(date(2026, 3, 31))

    assert values(municipality, "economic.assignments_year") == {(2026, 3): 2}


def test_an_indicator_no_longer_reported_loses_this_months_value(demo_dashboard):
    municipality = make_municipality("Noetinger")
    enable_dashboards(municipality, [demo_dashboard])
    take_snapshots(date(2026, 3, 10))
    module = registry.get_module(demo_dashboard)
    registry.register(
        DashboardModule(
            key=module.key,
            router=module.router,
            get_summary=lambda ctx, as_of: [],
            indicators=module.indicators,
        )
    )

    take_snapshots(date(2026, 3, 11))

    assert rows(municipality) == []


def test_a_failing_municipality_is_rolled_back_alone(demo_dashboard):
    noetinger, saira = make_municipality("Noetinger"), make_municipality("Saira")
    enable_dashboards(noetinger, [demo_dashboard])
    enable_dashboards(saira, [demo_dashboard])

    def summary(ctx, as_of):
        if ctx.municipality_id == saira.id:
            raise RuntimeError("broken")
        return [registry.SummaryIndicator("demo.day", as_of.day)]

    registry.register(
        DashboardModule(
            key="demo",
            router=registry.get_module("demo").router,
            get_summary=summary,
            indicators=(IndicatorDefinition("demo.day", reconstructible=True),),
        )
    )

    report = take_snapshots(date(2026, 3, 10), since=(2026, 2))

    assert report.failed == ["saira"]
    assert report.municipalities == 1
    assert values(noetinger, "demo.day") == {(2026, 2): 28, (2026, 3): 10}
    assert rows(saira) == []


def test_the_command_rebuilds_from_a_month_and_is_safe_to_repeat(monkeypatch):
    monkeypatch.setattr(cli, "get_today", lambda: date(2026, 4, 15))
    municipality = economic_member("viewer")
    economic_data(municipality, [date(2026, 1, 10), date(2026, 3, 2)])
    runner = CliRunner()

    first = runner.invoke(cli.app, ["snapshot-indicators", "--from", "2026-01"])
    count = len(rows())
    second = runner.invoke(cli.app, ["snapshot-indicators", "--from", "2026-01"])

    assert first.exit_code == 0, first.output
    assert "Snapshot of 2026-04 taken for 1 municipalities." in first.output
    assert "Rebuilt 2026-01 to 2026-03." in first.output
    assert second.exit_code == 0
    assert "0 rows written or changed." in second.output
    assert len(rows()) == count == 7


@pytest.mark.parametrize("month", ["2026-13", "26-01", "enero", "2026-5"])
def test_the_command_rejects_a_malformed_month(month):
    result = CliRunner().invoke(cli.app, ["snapshot-indicators", "--from", month])

    assert result.exit_code == 2
    assert "YYYY-MM" in result.output


def test_the_command_rejects_a_month_that_has_not_started(monkeypatch):
    monkeypatch.setattr(cli, "get_today", lambda: date(2026, 4, 15))

    result = CliRunner().invoke(cli.app, ["snapshot-indicators", "--from", "2026-05"])

    assert result.exit_code == 2
    assert rows() == []
