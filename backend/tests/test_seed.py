from sqlalchemy import func, select

from gobernar360.core.db import platform_session, tenant_session
from gobernar360.dashboards.projects.models import Milestone, Project
from gobernar360.platform.models import Municipality, User
from gobernar360.seed import DEMO_PASSWORD, seed_demo
from tests.factories import login, make_user


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_seed_demo_is_idempotent_and_creates_two_isolated_municipalities():
    seed_demo()
    seed_demo()

    with platform_session() as db:
        municipalities = {m.slug: m for m in db.scalars(select(Municipality))}
        user_count = _count(db, User)
    assert sorted(municipalities) == ["comuna-demo", "noetinger"]
    assert user_count == 6
    with tenant_session(municipalities["noetinger"].id) as db:
        assert _count(db, Project) >= 10
        assert _count(db, Milestone) >= 5
    with tenant_session(municipalities["comuna-demo"].id) as db:
        assert _count(db, Project) == 2


def test_seed_demo_with_reset_removes_previous_data():
    make_user("old@example.test")

    seed_demo(reset=True)

    with platform_session() as db:
        emails = set(db.scalars(select(User.email)))
    assert "old@example.test" not in emails
    assert "operador@gobernar360.test" in emails


def test_seeded_accounts_can_sign_in_with_their_roles(client):
    seed_demo()

    editor = login(client, "carga@noetinger.test", DEMO_PASSWORD).json()
    client.post("/api/auth/logout")
    no_access = login(client, "sinacceso@noetinger.test", DEMO_PASSWORD).json()
    client.post("/api/auth/logout")
    operator = login(client, "operador@gobernar360.test", DEMO_PASSWORD).json()

    assert editor["dashboards"] == [{"key": "projects", "level": "editor"}]
    assert no_access["dashboards"] == []
    assert operator["user"]["is_platform_operator"] is True
    assert operator["memberships"] == []


def test_seeded_summary_shows_a_mix_of_statuses(client):
    seed_demo()
    login(client, "lectura@noetinger.test", DEMO_PASSWORD)
    term_id = client.get("/api/dashboards/projects/terms").json()[0]["id"]

    summary = client.get("/api/dashboards/projects/summary", params={"term_id": term_id}).json()

    assert all(count > 0 for count in summary["status_counts"].values())
    assert summary["milestones"]["in_alert"] > 0
    assert summary["budget"]["planned_ratio"] is not None
