from sqlalchemy import delete, func, select

from gobernar360.core.db import platform_session, tenant_session
from gobernar360.dashboards.economic.models import (
    Actor,
    ActorPerson,
    ActorType,
    Assignment,
    EconomicPerson,
    Sector,
    Tool,
    ToolCategory,
    ToolSubcategory,
)
from gobernar360.dashboards.environment.models import Subcategory, Value, Variable
from gobernar360.dashboards.projects.models import Milestone, Project
from gobernar360.platform.models import (
    DashboardGrant,
    Municipality,
    MunicipalityDashboard,
    Person,
    User,
)
from gobernar360.seed import DEMO_PASSWORD, seed_demo
from tests.factories import admin_session, login, make_user


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

    assert editor["dashboards"] == [
        {"key": "economic", "level": "editor"},
        {"key": "environment", "level": "editor"},
        {"key": "projects", "level": "editor"},
    ]
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


def test_seed_demo_adds_the_environment_dashboard_to_an_older_demo_database():
    seed_demo()
    # A database seeded before the environment dashboard existed.
    with admin_session() as session, session.begin():
        for model in (Value, Variable, Subcategory):
            session.execute(delete(model))
        for model in (DashboardGrant, MunicipalityDashboard):
            session.execute(delete(model).where(model.dashboard_key == "environment"))
    with platform_session() as db:
        noetinger_id = db.scalar(select(Municipality.id).where(Municipality.slug == "noetinger"))
        users_before = _count(db, User)
    with tenant_session(noetinger_id) as db:
        projects_before = _count(db, Project)

    changed = seed_demo()
    changed_again = seed_demo()

    assert (changed, changed_again) == (True, False)
    with platform_session() as db:
        assert _count(db, User) == users_before
    with tenant_session(noetinger_id) as db:
        assert _count(db, Project) == projects_before
        assert _count(db, Variable) >= 8
        variable_count = _count(db, Variable)
    seed_demo()
    with tenant_session(noetinger_id) as db:
        assert _count(db, Variable) == variable_count


def test_seeded_environment_summary_has_loads_and_met_and_missed_targets(client):
    seed_demo()
    login(client, "lectura@noetinger.test", DEMO_PASSWORD)

    summary = client.get("/api/dashboards/environment/summary").json()

    assert summary["variable_count"] >= 8
    assert 0 < summary["loaded"] < summary["expected"]
    assert summary["targets_met"] > 0
    assert summary["targets_missed"] > 0
    used = [c["category"] for c in summary["categories"] if c["variables"]]
    assert "energy" in used
    assert "air" not in used


def test_seeded_environment_data_stays_inside_noetinger(client):
    seed_demo()
    login(client, "admin@comuna-demo.test", DEMO_PASSWORD)

    assert client.get("/api/dashboards/environment/variables").json() == []


def test_seed_demo_survives_a_demo_database_without_the_second_municipality():
    seed_demo()
    with admin_session() as session, session.begin():
        for model in (Value, Variable, Subcategory):
            session.execute(delete(model))
        for model in (DashboardGrant, MunicipalityDashboard):
            session.execute(delete(model).where(model.dashboard_key == "environment"))
        commune = session.scalar(select(Municipality).where(Municipality.slug == "comuna-demo"))
        commune.slug = "renombrada"

    assert seed_demo() is True

    with platform_session() as db:
        noetinger_id = db.scalar(select(Municipality.id).where(Municipality.slug == "noetinger"))
    with tenant_session(noetinger_id) as db:
        assert _count(db, Variable) >= 8


# Children first, so the rows can be deleted without tripping foreign keys.
ECONOMIC_MODELS = (
    Assignment,
    ActorPerson,
    EconomicPerson,
    Actor,
    Tool,
    ToolSubcategory,
    ToolCategory,
    Sector,
    ActorType,
    Person,
)


def test_seed_demo_adds_the_economic_dashboard_to_an_older_demo_database():
    seed_demo()
    # A database seeded before the economic dashboard existed.
    with admin_session() as session, session.begin():
        for model in ECONOMIC_MODELS:
            session.execute(delete(model))
        for model in (DashboardGrant, MunicipalityDashboard):
            session.execute(delete(model).where(model.dashboard_key == "economic"))
    with platform_session() as db:
        noetinger_id = db.scalar(select(Municipality.id).where(Municipality.slug == "noetinger"))
        users_before = _count(db, User)
    with tenant_session(noetinger_id) as db:
        projects_before, variables_before = _count(db, Project), _count(db, Variable)

    changed = seed_demo()
    changed_again = seed_demo()

    assert (changed, changed_again) == (True, False)
    with platform_session() as db:
        assert _count(db, User) == users_before
    with tenant_session(noetinger_id) as db:
        assert (_count(db, Project), _count(db, Variable)) == (projects_before, variables_before)
        assert _count(db, Actor) >= 10
        assert _count(db, EconomicPerson) == _count(db, Person) >= 10


def test_seeded_economic_summary_has_actors_people_and_assignments(client):
    seed_demo()
    login(client, "lectura@noetinger.test", DEMO_PASSWORD)

    summary = client.get("/api/dashboards/economic/summary").json()
    reports = client.get("/api/dashboards/economic/reports").json()

    assert summary["actors"]["total"] >= 10
    assert summary["people"]["total"] >= 10
    assert 0 < summary["actors"]["with_assignments"] < summary["actors"]["total"]
    assert 0 < summary["people"]["with_assignments"] < summary["people"]["total"]
    assert summary["tools"] >= 5
    assert summary["actor_tools"] and summary["person_tools"]
    assert len(reports["actors_by_type"]) >= 3
    assert len(reports["people_by_employment_status"]) >= 3
    last_year = client.get(
        "/api/dashboards/economic/summary", params={"year": summary["year"] - 1}
    ).json()
    assert last_year["assignments"] > 0


def test_seeded_economic_data_stays_inside_noetinger(client):
    seed_demo()
    login(client, "admin@comuna-demo.test", DEMO_PASSWORD)

    assert client.get("/api/dashboards/economic/actors").json() == {"items": [], "total": 0}
    assert client.get("/api/dashboards/economic/people").json() == {"items": [], "total": 0}
    assert client.get("/api/dashboards/economic/tools").json() == []
