import io
import json
from datetime import date
from pathlib import Path

import pypdf
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from gobernar360.core.db import platform_session, tenant_session
from gobernar360.dashboards import registry
from gobernar360.dashboards.complaints import models as complaints
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
from gobernar360.platform.access import system_context
from gobernar360.platform.indicators import month_of, shift
from gobernar360.platform.models import (
    DashboardGrant,
    DashboardStatus,
    IndicatorSnapshot,
    IndicatorTarget,
    MonthlyReport,
    Municipality,
    MunicipalityDashboard,
    Person,
    PublicSettings,
    PublicSite,
    PublishedDashboard,
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


# The complaints dashboard came last and points at the registry, so it goes first of all.
COMPLAINTS_MODELS = (
    complaints.ComplaintEvent,
    complaints.Complaint,
    complaints.ComplaintType,
    complaints.Holiday,
    complaints.WorkingWeek,
    complaints.Zone,
    complaints.Area,
)
# Children first, so the rows can be deleted without tripping foreign keys.
SOCIAL_MODELS = (
    *COMPLAINTS_MODELS,
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
            session.execute(
                delete(model).where(model.dashboard_key.in_(["economic", "social", "complaints"]))
            )
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
            session.execute(delete(model).where(model.dashboard_key.in_(["social", "complaints"])))
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


COMPLAINTS_API = "/api/dashboards/complaints"


def _noetinger_id():
    with platform_session() as db:
        return db.scalar(select(Municipality.id).where(Municipality.slug == "noetinger"))


def test_seeded_noetinger_has_a_year_of_indicator_history_and_targets(client):
    seed_demo()
    today = date.today()
    login(client, "admin@noetinger.test", DEMO_PASSWORD)

    for section in client.get("/api/overview").json():
        for indicator in section["indicators"]:
            values = [point["value"] for point in indicator["series"]]
            assert all(value is not None for value in values), indicator["key"]
            assert indicator["last_year_value"] is not None, indicator["key"]
    evolution = {
        item["key"]: item for item in client.get("/api/dashboards/projects/evolution").json()
    }
    delayed = evolution["projects.delayed"]
    # Met, so an administrator can tighten it and watch it be missed.
    assert delayed["target"] is not None and delayed["on_track"] is True
    assert any(item["on_track"] is False for item in evolution.values())
    with admin_session() as session:
        years = set(session.scalars(select(IndicatorTarget.year)))
    assert years == {today.year - 1, today.year}
    assert client.get("/api/overview/combined").json()


def test_seeded_history_stays_inside_noetinger(client):
    seed_demo()
    login(client, "admin@comuna-demo.test", DEMO_PASSWORD)

    evolution = client.get("/api/dashboards/projects/evolution").json()

    assert all(item["previous_value"] is None for item in evolution)
    assert all(item["target"] is None for item in evolution)


def test_seed_demo_adds_indicator_history_to_an_older_demo_database_once():
    seed_demo()
    with admin_session() as session:
        counts = _count(session, IndicatorSnapshot), _count(session, IndicatorTarget)
    # A database seeded before indicators had history.
    with admin_session() as session, session.begin():
        session.execute(delete(IndicatorSnapshot))
        session.execute(delete(IndicatorTarget))

    changed = seed_demo()
    changed_again = seed_demo()

    assert (changed, changed_again) == (True, False)
    with admin_session() as session:
        assert (_count(session, IndicatorSnapshot), _count(session, IndicatorTarget)) == counts


def test_seeded_dashboards_report_only_indicators_of_their_catalogue():
    seed_demo()

    with tenant_session(_noetinger_id()) as db:
        context = system_context(db, _noetinger_id())
        for module in registry.all_modules():
            reported = module.get_summary(context, date.today())
            assert reported, module.key
            for indicator in reported:
                definition = module.indicator(indicator.key)
                assert definition is not None, indicator.key
                assert definition.unit == indicator.unit, indicator.key


def test_seeded_noetinger_has_closed_reports_and_a_public_page_with_nothing_else_chosen(client):
    seed_demo()
    today = date.today()
    login(client, "admin@noetinger.test", DEMO_PASSWORD)

    reports = client.get("/api/reports").json()
    last_month = shift(month_of(today), -1)

    closed = {(r["year"], r["month"]) for r in reports if r["status"] == "closed"}
    assert closed == {shift(month_of(today), -ago) for ago in (2, 3, 4)}
    assert last_month not in {(r["year"], r["month"]) for r in reports}
    assert sorted(r["status"] for r in reports if r["version"] == 2) == ["closed"]
    assert not any(r["published"] for r in reports)
    publication = client.get("/api/publication").json()
    assert (publication["enabled"], publication["slug"]) == (True, "noetinger")
    published = [d["key"] for d in publication["dashboards"] if d["published"]]
    assert published == ["projects", "social"]
    assert not any(i["published"] for d in publication["dashboards"] for i in d["indicators"])
    page = client.get("/api/public/noetinger").json()
    assert [d["key"] for d in page["dashboards"]] == ["projects", "social"]
    assert (page["indicators"], page["reports"]) == ([], [])


def test_seeded_comuna_demo_has_no_reports_and_no_public_page(client):
    seed_demo()
    login(client, "admin@comuna-demo.test", DEMO_PASSWORD)

    assert client.get("/api/reports").json() == []
    assert client.get("/api/publication").json()["enabled"] is False
    assert client.get("/api/public/comuna-demo").status_code == 404


def test_seed_demo_adds_reports_and_the_public_page_to_an_older_demo_database_once():
    seed_demo()
    with admin_session() as session, session.begin():
        for model in (PublicSite, MonthlyReport, PublishedDashboard, PublicSettings):
            session.execute(delete(model))

    changed = seed_demo()
    changed_again = seed_demo()

    assert (changed, changed_again) == (True, False)
    with admin_session() as session:
        assert _count(session, MonthlyReport) == 4
        assert _count(session, PublicSite) == 1


def _registry_people() -> list[tuple[str, str, str | None]]:
    with admin_session() as session:
        return list(session.execute(select(Person.first_name, Person.last_name, Person.dni)))


def _mentions(text: str, people) -> list[str]:
    """Names, in either order, and document numbers, with or without thousands dots."""
    found = []
    lowered = text.lower()
    for first, last, dni in people:
        for name in (f"{first} {last}", f"{last} {first}", f"{last}, {first}"):
            if name.lower() in lowered:
                found.append(name)
        if dni and (dni in text or f"{int(dni):,}".replace(",", ".") in text):
            found.append(dni)
    return found


def test_nothing_published_or_reported_names_anyone_of_the_people_registry(client):
    seed_demo()
    login(client, "admin@noetinger.test", DEMO_PASSWORD)
    people = _registry_people()
    assert len(people) > 20
    # Everything that can be published, and last month's report.
    for dashboard in client.get("/api/publication").json()["dashboards"]:
        client.put(f"/api/publication/dashboards/{dashboard['key']}", json={"published": True})
        for indicator in dashboard["indicators"]:
            client.put(f"/api/publication/indicators/{indicator['key']}", json={"published": True})
    year, month = shift(month_of(date.today()), -1)
    report = client.post(
        f"/api/reports/{year}/{month}/close", json={"comments": {"social": "Mes tranquilo."}}
    ).json()
    assert (
        client.put(f"/api/reports/{report['id']}/publication", json={"published": True}).status_code
        == 204
    )
    anonymous = TestClient(client.app)

    page = anonymous.get("/api/public/noetinger")
    public_pdf = anonymous.get(f"/api/public/noetinger/reports/{year}/{month}").content
    internal_pdf = client.get(f"/api/reports/{report['id']}/pdf").content

    assert len(page.json()["indicators"]) > 15
    for name, document in (
        ("public page", page.text),
        ("public report", _pdf_text(public_pdf)),
        ("internal report", _pdf_text(internal_pdf)),
    ):
        assert _mentions(document, people) == [], name


def _pdf_text(data: bytes) -> str:
    return "\n".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(data)).pages)


def test_catalogue_names_match_the_web_apps_texts():
    seed_demo()
    locale = json.loads(
        (Path(__file__).resolve().parents[2] / "frontend/src/locales/es-AR.json").read_text()
    )
    for module in registry.all_modules():
        assert module.name == locale[module.key]["title"], module.key
        for definition in module.indicators:
            assert definition.name == locale["overview"]["indicators"][definition.key]


def test_seeded_complaints_wait_for_the_operator_in_noetinger(client):
    seed_demo()

    with platform_session() as db:
        enabled = {
            (row.municipality_id, row.dashboard_key)
            for row in db.scalars(select(MunicipalityDashboard))
        }
        commune_id = db.scalar(select(Municipality.id).where(Municipality.slug == "comuna-demo"))
    assert (_noetinger_id(), "complaints") not in enabled
    assert (commune_id, "complaints") in enabled
    login(client, "admin@noetinger.test", DEMO_PASSWORD)
    assert client.get(f"{COMPLAINTS_API}/complaints").status_code == 403
    with tenant_session(_noetinger_id()) as db:
        count = _count(db, complaints.Complaint)
        states = set(db.scalars(select(complaints.Complaint.state)))
        identified = db.scalar(
            select(func.count()).where(complaints.Complaint.person_id.is_not(None))
        )
        retired = db.scalar(
            select(func.count()).where(complaints.ComplaintType.is_active.is_(False))
        )
    assert count >= 300
    assert states == {
        "received",
        "assigned",
        "in_progress",
        "waiting",
        "resolved",
        "closed",
        "rejected",
        "reopened",
    }
    assert 0 < identified < count
    assert retired == 1


def test_seeded_complaints_give_a_year_of_analysis_once_enabled(client):
    seed_demo()
    with admin_session() as session, session.begin():
        session.add(
            MunicipalityDashboard(municipality_id=_noetinger_id(), dashboard_key="complaints")
        )
    login(client, "admin@noetinger.test", DEMO_PASSWORD)

    summary = client.get(f"{COMPLAINTS_API}/summary").json()
    queues = client.get(f"{COMPLAINTS_API}/queues").json()
    overview = client.get("/api/overview").json()

    assert summary["totals"]["received"] >= 300
    assert 0.3 < summary["totals"]["on_time_ratio"] < 0.9
    assert len(summary["monthly"]) == 12
    assert all(month["received"] > 0 and month["resolved"] > 0 for month in summary["monthly"])
    assert len(summary["by_type"]) >= 10 and len(summary["by_area"]) >= 5
    medians = {row["median_days"] for row in summary["by_type"]}
    assert len(medians) > 3
    backlog = summary["backlog"]
    assert backlog["open"] > 0 and backlog["overdue"] > 0 and backlog["paused"] > 0
    assert summary["repeated"] and len(summary["top_zones"]) == 6
    assert sum(queue["open"] for queue in queues) == backlog["open"]
    section = next(s for s in overview if s["dashboard_key"] == "complaints")
    assert [i["key"] for i in section["indicators"]] == [
        "complaints.open",
        "complaints.overdue",
        "complaints.on_time_ratio",
        "complaints.median_resolution_days",
    ]
    assert len(section["status"]) == 6
    lucia = client.get(f"{COMPLAINTS_API}/people/lookup", params={"dni": "33123456"}).json()
    assert lucia["person"]["full_name"] == "Fernández, Lucía"


def test_seeded_complaints_stay_inside_noetinger(client):
    seed_demo()
    login(client, "admin@comuna-demo.test", DEMO_PASSWORD)

    listed = client.get(f"{COMPLAINTS_API}/complaints").json()
    types = client.get(f"{COMPLAINTS_API}/types").json()

    assert listed["total"] == 4
    assert {item["area"]["name"] for item in listed["items"]} == {"Servicios Públicos"}
    assert {t["name"] for t in types} == {"Luminaria apagada", "Camino rural intransitable"}
    assert client.get(f"{COMPLAINTS_API}/calendar").json()["holidays"] == []


def test_seed_demo_adds_the_complaints_to_an_older_demo_database_once():
    seed_demo()
    # A database seeded before the complaints dashboard existed.
    with admin_session() as session, session.begin():
        for model in COMPLAINTS_MODELS:
            session.execute(delete(model))
        session.execute(
            delete(DashboardStatus).where(DashboardStatus.dashboard_key == "complaints")
        )
        for model in (DashboardGrant, MunicipalityDashboard):
            session.execute(delete(model).where(model.dashboard_key == "complaints"))
    with tenant_session(_noetinger_id()) as db:
        projects_before, people_before = _count(db, Project), _count(db, Person)

    changed = seed_demo()
    changed_again = seed_demo()

    assert (changed, changed_again) == (True, False)
    with tenant_session(_noetinger_id()) as db:
        assert _count(db, Project) == projects_before
        # Complainants already in the registry are reused, not loaded twice.
        assert _count(db, Person) == people_before
        assert _count(db, complaints.Complaint) >= 300
