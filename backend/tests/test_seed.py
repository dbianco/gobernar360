from datetime import date

from sqlalchemy import delete, func, select

from gobernar360.core.db import platform_session, tenant_session
from gobernar360.dashboards.cabinet.models import (
    AgendaItem,
    Attendee,
    Carryover,
    Meeting,
    Taken,
)
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
from gobernar360.dashboards.procedures.models import (
    Area,
    Procedure,
    ProcedureRequirement,
    Requirement,
    Source,
)
from gobernar360.dashboards.projects.models import Milestone, Project
from gobernar360.dashboards.social.models import (
    Benefit,
    BenefitCategory,
    Delivery,
    Household,
    Intervention,
    InterventionType,
    SocialPerson,
)
from gobernar360.platform.commitment_models import Commitment, CommitmentEntry
from gobernar360.platform.models import (
    DashboardGrant,
    DashboardStatus,
    Municipality,
    MunicipalityDashboard,
    Person,
    User,
)
from gobernar360.seed import DEMO_PASSWORD, INFORMAL_COMMITMENTS, seed_demo
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
        {"key": "cabinet", "level": "editor"},
        {"key": "economic", "level": "editor"},
        {"key": "environment", "level": "editor"},
        {"key": "procedures", "level": "editor"},
        {"key": "projects", "level": "editor"},
        {"key": "social", "level": "editor"},
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
SOCIAL_MODELS = (
    Delivery,
    Intervention,
    SocialPerson,
    Household,
    Benefit,
    BenefitCategory,
    InterventionType,
)
# The social dashboard came later and shares the registry, so it goes first.
ECONOMIC_MODELS = (
    *SOCIAL_MODELS,
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
            session.execute(delete(model).where(model.dashboard_key.in_(["economic", "social"])))
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
        assert _count(db, Person) >= _count(db, EconomicPerson) >= 10
        assert _count(db, SocialPerson) >= 12


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


def test_seed_demo_adds_the_social_dashboard_to_an_older_demo_database():
    seed_demo()
    # A database seeded before the social dashboard existed.
    with admin_session() as session, session.begin():
        for model in SOCIAL_MODELS:
            session.execute(delete(model))
        session.execute(delete(Person).where(Person.id.not_in(select(EconomicPerson.person_id))))
        for model in (DashboardGrant, MunicipalityDashboard):
            session.execute(delete(model).where(model.dashboard_key == "social"))
    with platform_session() as db:
        noetinger_id = db.scalar(select(Municipality.id).where(Municipality.slug == "noetinger"))
        users_before = _count(db, User)
    with tenant_session(noetinger_id) as db:
        before = [_count(db, model) for model in (Project, Variable, Actor, EconomicPerson)]

    changed = seed_demo()
    changed_again = seed_demo()

    assert (changed, changed_again) == (True, False)
    with platform_session() as db:
        assert _count(db, User) == users_before
    with tenant_session(noetinger_id) as db:
        assert [_count(db, model) for model in (Project, Variable, Actor, EconomicPerson)] == before
        assert _count(db, SocialPerson) >= 12


def test_seeded_social_summary_has_people_households_and_records(client):
    seed_demo()
    login(client, "lectura@noetinger.test", DEMO_PASSWORD)

    summary = client.get("/api/dashboards/social/summary").json()
    reports = client.get("/api/dashboards/social/reports").json()

    assert summary["people"] >= 12
    assert summary["households"] >= 4
    assert 0 < summary["people_with_deliveries"] < summary["people"]
    assert summary["deliveries"] >= 8 and summary["units"] > summary["deliveries"]
    assert summary["interventions"] >= 5
    assert len(summary["benefits"]) >= 3 and len(summary["intervention_types"]) >= 3
    assert len(reports["people_by_neighborhood"]) >= 3
    last_year = client.get(
        "/api/dashboards/social/summary", params={"year": summary["year"] - 1}
    ).json()
    assert last_year["deliveries"] > 0 and last_year["interventions"] > 0
    households = client.get("/api/dashboards/social/households").json()["items"]
    assert any(h["head"] for h in households) and all(h["member_count"] for h in households)


def test_seeded_social_people_share_the_registry_with_economic():
    seed_demo()

    with platform_session() as db:
        noetinger_id = db.scalar(select(Municipality.id).where(Municipality.slug == "noetinger"))
    with tenant_session(noetinger_id) as db:
        shared = db.scalar(
            select(func.count())
            .select_from(SocialPerson)
            .where(SocialPerson.person_id.in_(select(EconomicPerson.person_id)))
        )
        documents = db.scalars(select(Person.dni).where(Person.dni.is_not(None))).all()
        assert shared >= 2
        assert _count(db, SocialPerson) > shared
        assert len(documents) == len(set(documents))


def test_seeded_social_data_stays_inside_noetinger(client):
    seed_demo()
    login(client, "admin@comuna-demo.test", DEMO_PASSWORD)

    assert client.get("/api/dashboards/social/people").json() == {"items": [], "total": 0}
    assert client.get("/api/dashboards/social/households").json() == {"items": [], "total": 0}
    assert client.get("/api/dashboards/social/benefits").json() == []
    assert client.get("/api/dashboards/social/interventions").json() == {"items": [], "total": 0}


def test_seeded_noetinger_has_lights_in_every_dashboard(client):
    seed_demo()
    login(client, "admin@noetinger.test", DEMO_PASSWORD)

    overview = client.get("/api/overview").json()

    assert {section["dashboard_key"] for section in overview} == {
        "projects",
        "environment",
        "economic",
        "social",
        "procedures",
        "cabinet",
    }
    assert all(len(section["status"]) == 6 for section in overview)
    colors = {light["color"] for section in overview for light in section["status"]}
    assert colors == {"green", "yellow", "red"}


def test_seeded_lights_stay_inside_noetinger(client):
    seed_demo()
    login(client, "admin@comuna-demo.test", DEMO_PASSWORD)

    assert all(section["status"] == [] for section in client.get("/api/overview").json())


def test_seed_demo_adds_lights_to_an_older_demo_database_once():
    seed_demo()
    # A database seeded before status lights existed.
    with admin_session() as session, session.begin():
        session.execute(delete(DashboardStatus))

    changed = seed_demo()
    changed_again = seed_demo()

    assert (changed, changed_again) == (True, False)
    with admin_session() as session:
        assert _count(session, DashboardStatus) == 24


PROCEDURES_API = "/api/dashboards/procedures"


def test_seeded_procedures_inventory_shows_opportunities(client):
    seed_demo()
    login(client, "lectura@noetinger.test", DEMO_PASSWORD)

    summary = client.get(f"{PROCEDURES_API}/summary").json()
    opportunities = client.get(f"{PROCEDURES_API}/opportunities").json()

    assert summary["procedures"] >= 10
    assert 0 < summary["online"] < summary["procedures"]
    assert len(summary["top_requirements"]) == 10
    levels = [row["source"]["level"] for row in opportunities["sources"]]
    assert levels.count("municipal") >= 3
    assert {"provincial", "national"} <= set(levels)
    assert opportunities["without_source"]["procedures"] > 0
    inactive = client.get(f"{PROCEDURES_API}/procedures", params={"active": "false"}).json()
    assert inactive["total"] >= 1


def test_seeded_procedures_stay_inside_noetinger(client):
    seed_demo()
    login(client, "admin@comuna-demo.test", DEMO_PASSWORD)

    assert client.get(f"{PROCEDURES_API}/summary").json()["procedures"] == 0
    assert client.get(f"{PROCEDURES_API}/areas").json() == []


def test_seed_demo_adds_the_procedures_dashboard_to_an_older_demo_database():
    seed_demo()
    # A database seeded before the procedures dashboard existed.
    with admin_session() as session, session.begin():
        for model in (ProcedureRequirement, Procedure, Requirement, Source, Area):
            session.execute(delete(model))
        for model in (DashboardGrant, MunicipalityDashboard, DashboardStatus):
            session.execute(delete(model).where(model.dashboard_key == "procedures"))
    with admin_session() as session:
        lights_before = _count(session, DashboardStatus)

    changed = seed_demo()
    changed_again = seed_demo()

    assert (changed, changed_again) == (True, False)
    with admin_session() as session:
        assert _count(session, Procedure) >= 10
        assert _count(session, DashboardStatus) == lights_before + 6
        procedures_count = _count(session, Procedure)
    seed_demo()
    with admin_session() as session:
        assert _count(session, Procedure) == procedures_count


CABINET_API = "/api/dashboards/cabinet"


def test_seeded_cabinet_has_closed_meetings_with_linked_commitments(client):
    seed_demo()
    login(client, "lectura@noetinger.test", DEMO_PASSWORD)

    meetings = client.get(f"{CABINET_API}/meetings").json()
    commitments = client.get(f"{CABINET_API}/commitments").json()["items"]
    summary = client.get(f"{CABINET_API}/summary").json()

    assert meetings["total"] == 3 and all(m["closed"] for m in meetings["items"])
    linked = [c["subject"] for c in commitments if c["subject"]]
    assert {s["kind"] for s in linked} == {"project", "month"}
    assert {s["color"] for s in linked if s["kind"] == "month"} == {"red"}
    assert all(s["access"] == "visible" for s in linked)
    assert all(count > 0 for count in summary["by_state"].values())
    assert [c["times_postponed"] for c in summary["most_postponed"]] == [2, 1]
    assert 0 < summary["on_time_share"] < 1


def test_seeded_minutes_tell_what_was_true_at_each_meeting(client):
    seed_demo()
    login(client, "admin@noetinger.test", DEMO_PASSWORD)
    latest, middle, first = client.get(f"{CABINET_API}/meetings").json()["items"]

    def minutes(meeting):
        return client.get(f"{CABINET_API}/meetings/{meeting['id']}/minutes.html").text

    assert "venían de reuniones anteriores" not in minutes(first)
    assert "vencido" not in minutes(first)
    assert "postergado una vez" in minutes(middle)
    # Delivered before the second meeting, so it never reached it.
    assert "ejecución presupuestaria del trimestre" not in minutes(middle)
    assert "postergado 2 veces" in minutes(latest)


def test_seeded_noetinger_can_prepare_its_next_meeting(client):
    seed_demo()
    login(client, "admin@noetinger.test", DEMO_PASSWORD)

    today = date.today().isoformat()
    answer = client.get(f"{CABINET_API}/agenda-proposal", params={"date": today}).json()

    sources = [(p["source"], p["carried"]) for p in answer["proposals"]]
    assert sources == [
        ("light", False),
        ("light", False),
        ("light", False),
        ("commitment", False),
        ("commitment", False),
        ("manual", True),
    ]
    assert answer["to_carry_over"] == 4


def test_seeded_cabinet_stays_inside_noetinger(client):
    seed_demo()
    login(client, "admin@comuna-demo.test", DEMO_PASSWORD)

    assert client.get(f"{CABINET_API}/meetings").json() == {"items": [], "total": 0}
    assert client.get(f"{CABINET_API}/commitments").json() == {"items": [], "total": 0}


# Children first, as the rest of the tables a reset would empty.
CABINET_MODELS = (CommitmentEntry, Carryover, Taken, Attendee, AgendaItem, Commitment, Meeting)


def _forget_cabinet() -> None:
    """Leave the database as seeded before the cabinet dashboard existed."""
    with admin_session() as session, session.begin():
        for model in CABINET_MODELS:
            session.execute(delete(model))
        for model in (DashboardGrant, MunicipalityDashboard, DashboardStatus):
            session.execute(delete(model).where(model.dashboard_key == "cabinet"))


def test_seed_demo_adds_the_cabinet_dashboard_to_an_older_demo_database():
    seed_demo()
    _forget_cabinet()

    assert (seed_demo(), seed_demo()) == (True, False)

    with admin_session() as session:
        assert (_count(session, Meeting), _count(session, Taken)) == (3, 8)


def test_seed_demo_adds_the_cabinet_to_a_demo_database_that_lost_its_projects():
    seed_demo()
    _forget_cabinet()
    with admin_session() as session, session.begin():
        for project in session.scalars(select(Project)).unique():
            project.name = f"{project.name} (renombrado)"

    assert seed_demo() is True

    with admin_session() as session:
        assert _count(session, Taken) == 8


def test_seeded_people_have_commitments_outside_meetings_and_news_about_them(client):
    seed_demo()
    seen = {}
    for name in ("admin", "carga", "lectura", "sinacceso"):
        login(client, f"{name}@noetinger.test", DEMO_PASSWORD)
        rows = client.get("/api/notifications").json()
        seen[name] = [
            (row["description"], row["state"], [news["kind"] for news in row["news"]])
            for row in rows["mine"] + rows["others"]
            if row["description"] in {row[0] for row in INFORMAL_COMMITMENTS}
        ]

    note, suppliers, photos, hall = (row[0] for row in INFORMAL_COMMITMENTS)
    assert seen == {
        "admin": [(hall, "done", ["done"]), (note, "open", []), (photos, "open", [])],
        "carga": [
            (suppliers, "overdue", []),
            (note, "open", ["assigned"]),
            (hall, "done", ["done"]),
            (photos, "open", []),
        ],
        "lectura": [(photos, "open", ["assigned"]), (note, "open", [])],
        "sinacceso": [],
    }


def test_seed_demo_adds_informal_commitments_to_an_older_demo_database_once():
    seed_demo()
    with admin_session() as session, session.begin():
        session.execute(delete(Commitment).where(Commitment.source.is_(None)))

    assert (seed_demo(), seed_demo()) == (True, False)

    with admin_session() as session:
        assert _count(session, Commitment) == 8 + len(INFORMAL_COMMITMENTS)


def test_seed_demo_survives_a_demo_database_that_lost_the_people_who_give_commitments():
    seed_demo()
    with admin_session() as session, session.begin():
        session.execute(delete(Commitment).where(Commitment.source.is_(None)))
        reader = session.scalar(select(User).where(User.email == "lectura@noetinger.test"))
        reader.email = "otra@noetinger.test"

    assert seed_demo() is False
