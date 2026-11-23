"""Email notifications: overdue milestones and missing status lights, each sent once."""

from datetime import date, timedelta

import pytest
from sqlalchemy import update
from typer.testing import CliRunner

from gobernar360.cli import app as cli
from gobernar360.dashboards.projects.models import Milestone
from gobernar360.platform import notifications
from gobernar360.platform.models import DashboardStatus, EmailOutbox
from gobernar360.platform.texts import has_text
from tests.factories import (
    admin_session,
    configure,
    emails_to,
    login,
    make_membership,
    make_municipality,
    make_user,
)
from tests.projects.factories import make_axis, make_department, make_project, make_term

TODAY = date(2026, 11, 20)
LAST_MONTH = (2026, 10)


@pytest.fixture(autouse=True)
def dashboards(client):
    """The real dashboards are installed by the app the `client` fixture creates."""


def _municipality(name: str = "Noetinger", admin: str = "admin@noetinger.test"):
    municipality = make_municipality(name)
    make_membership(make_user(admin), municipality, admin=True, enable=["projects"])
    return municipality


def _light(municipality, key: str = "projects", year_month=LAST_MONTH) -> None:
    with admin_session() as session, session.begin():
        session.add(
            DashboardStatus(
                municipality_id=municipality.id,
                dashboard_key=key,
                year=year_month[0],
                month=year_month[1],
                color="green",
            )
        )


def _project(municipality, *milestones, name="Pavimentación", status="in_progress"):
    term = make_term(municipality)
    return make_project(
        municipality,
        term,
        make_axis(municipality, term),
        make_department(municipality),
        name=name,
        milestones=milestones,
        status=status,
    )


def _overdue(days: int = 5):
    return (TODAY - timedelta(days=days), None)


def test_an_overdue_milestone_is_emailed_once_however_many_runs(client):
    noetinger = _municipality()
    _light(noetinger)
    project = _project(noetinger, _overdue(), (TODAY + timedelta(days=10), None))

    first = notifications.notify(TODAY)
    second = notifications.notify(TODAY)
    third = notifications.notify(TODAY + timedelta(days=1))

    assert (first.emails, second.emails, third.emails) == (1, 0, 0)
    [email] = emails_to("admin@noetinger.test")
    link = f"http://localhost:5173/d/projects/projects/{project.id}"
    assert email.subject == "Hitos vencidos en Noetinger"
    assert f'<li><a href="{link}">Pavimentación</a>: «Hito 1», vencía el 15/11/2026.</li>' in (
        email.body_html
    )
    assert f"• Pavimentación ({link}): «Hito 1», vencía el 15/11/2026." in email.body
    assert "Hito 2" not in email.body
    assert "http://localhost:5173/account" in email.body


def test_milestones_that_become_overdue_later_are_new_events(client):
    noetinger = _municipality()
    _light(noetinger)
    _project(noetinger, _overdue(), (TODAY + timedelta(days=2), None))

    notifications.notify(TODAY)
    notifications.notify(TODAY + timedelta(days=3))

    first, second = emails_to("admin@noetinger.test")
    assert "Hito 1" in first.body and "Hito 2" not in first.body
    assert "Hito 2" in second.body and "Hito 1" not in second.body


def test_a_milestone_moved_to_a_new_date_that_passes_again_is_a_new_event(client):
    noetinger = _municipality()
    _light(noetinger)
    _project(noetinger, _overdue())
    notifications.notify(TODAY)
    with admin_session() as session, session.begin():
        session.execute(update(Milestone).values(due_date=TODAY + timedelta(days=1)))

    notifications.notify(TODAY + timedelta(days=2))

    assert len(emails_to("admin@noetinger.test")) == 2


def test_completed_milestones_and_finished_projects_raise_nothing(client):
    noetinger = _municipality()
    _light(noetinger)
    _project(noetinger, (TODAY - timedelta(days=9), TODAY - timedelta(days=8)))
    _project(noetinger, _overdue(), name="Terminado", status="finished")

    assert notifications.notify(TODAY).emails == 0


def test_only_the_administrators_of_the_dashboard_are_told(client):
    noetinger = _municipality()
    _light(noetinger)
    make_membership(make_user("editor@noetinger.test"), noetinger, grants={"projects": "editor"})
    make_membership(make_user("jefa@noetinger.test"), noetinger, grants={"projects": "admin"})
    make_membership(make_user("baja@noetinger.test", active=False), noetinger, admin=True)
    _project(noetinger, _overdue())

    notifications.notify(TODAY)

    assert len(emails_to("admin@noetinger.test")) == 1
    assert len(emails_to("jefa@noetinger.test")) == 1
    assert emails_to("editor@noetinger.test") == []
    assert emails_to("baja@noetinger.test") == []


def test_a_municipality_is_only_told_about_its_own_milestones(client):
    noetinger = _municipality()
    saira = _municipality("Saira", "admin@saira.test")
    _light(noetinger)
    _light(saira)
    _project(saira, _overdue(), name="Obra de Saira")

    notifications.notify(TODAY)

    assert emails_to("admin@noetinger.test") == []
    [email] = emails_to("admin@saira.test")
    assert "Obra de Saira" in email.body and email.subject == "Hitos vencidos en Saira"


def test_someone_in_two_municipalities_hears_about_each_separately(client):
    ana = make_user("ana@noetinger.test")
    noetinger, saira = make_municipality("Noetinger"), make_municipality("Saira")
    for municipality in (noetinger, saira):
        make_membership(ana, municipality, admin=True, enable=["projects"])
        _light(municipality)
        _project(municipality, _overdue(), name=f"Obra de {municipality.name}")

    notifications.notify(TODAY)

    emails = sorted(emails_to("ana@noetinger.test"), key=lambda email: email.subject)
    assert [email.subject for email in emails] == [
        "Hitos vencidos en Noetinger",
        "Hitos vencidos en Saira",
    ]
    assert "Obra de Noetinger" in emails[0].body and "Obra de Saira" not in emails[0].body


def test_a_dashboard_without_last_months_light_is_reported_once(client):
    noetinger = make_municipality("Noetinger")
    make_membership(
        make_user("admin@noetinger.test"),
        noetinger,
        admin=True,
        enable=["projects", "environment", "social"],
    )
    _light(noetinger, "environment")
    _light(noetinger, "social", (2026, 11))  # this month's does not count

    assert notifications.notify(TODAY).emails == 1
    assert notifications.notify(TODAY).emails == 0

    [email] = emails_to("admin@noetinger.test")
    assert email.subject == "Falta el estado mensual de octubre en Noetinger"
    assert "• Proyectos (http://localhost:5173/d/projects)" in email.body
    assert "• Social (http://localhost:5173/d/social)" in email.body
    assert "Ambiental" not in email.body


def test_the_next_month_is_a_new_event_and_january_looks_at_december(client):
    _municipality()

    notifications.notify(date(2027, 1, 5))
    notifications.notify(date(2027, 2, 5))

    subjects = [email.subject for email in emails_to("admin@noetinger.test")]
    assert subjects == [
        "Falta el estado mensual de diciembre en Noetinger",
        "Falta el estado mensual de enero en Noetinger",
    ]


def test_each_kind_can_be_turned_off_in_the_account(client):
    _municipality()
    login(client, "admin@noetinger.test")

    response = client.put("/api/auth/notifications/status_light_missing", json={"enabled": False})
    notifications.notify(TODAY)

    assert response.json() == {"kind": "status_light_missing", "enabled": False}
    assert emails_to("admin@noetinger.test") == []
    assert client.get("/api/auth/notifications").json() == [
        {"kind": "status_light_missing", "enabled": False},
        {"kind": "milestone_overdue", "enabled": True},
    ]


def test_turning_a_kind_back_on_resumes_it(client):
    noetinger = _municipality()
    _light(noetinger)
    _project(noetinger, _overdue())
    login(client, "admin@noetinger.test")
    client.put("/api/auth/notifications/milestone_overdue", json={"enabled": False})
    notifications.notify(TODAY)

    client.put("/api/auth/notifications/milestone_overdue", json={"enabled": True})
    notifications.notify(TODAY)

    assert len(emails_to("admin@noetinger.test")) == 1


def test_notification_settings_need_a_signed_in_user_and_a_known_kind(client):
    make_user("ana@noetinger.test")

    anonymous = client.get("/api/auth/notifications")
    login(client, "ana@noetinger.test")
    unknown = client.put("/api/auth/notifications/lottery_results", json={"enabled": False})

    assert anonymous.status_code == 401
    assert unknown.status_code == 404


def test_every_kind_of_notification_has_its_email_texts(client):
    for kind in notifications.all_kinds():
        for key in (f"email.templates.{kind}.subject", f"email.templates.{kind}.html"):
            assert has_text(key), key
        assert has_text(f"email.items.{kind}"), kind


def test_notify_command_run_twice_queues_the_email_once(client):
    noetinger = _municipality()
    _light(noetinger)
    _project(noetinger, _overdue(days=40))
    runner = CliRunner()

    first = runner.invoke(cli, ["notify", "--no-send"])
    second = runner.invoke(cli, ["notify", "--no-send"])

    assert first.exit_code == 0, first.output
    assert "Notification emails queued: 1" in first.output
    assert "Notification emails queued: 0" in second.output
    assert [email.status for email in emails_to("admin@noetinger.test")] == ["pending"]
    with admin_session() as session:
        assert session.query(EmailOutbox).count() == 1


# The municipality's own list of recipients and texts (Configuración)


def test_a_list_of_addresses_receives_every_alert_instead_of_the_administrators(client):
    noetinger = _municipality()
    configure(noetinger, ["jefa@noetinger.test", "prensa@example.test"])
    _project(noetinger, _overdue())

    notifications.notify(TODAY)

    assert emails_to("admin@noetinger.test") == []
    for address in ("jefa@noetinger.test", "prensa@example.test"):
        subjects = sorted(email.subject for email in emails_to(address))
        assert subjects == [
            "Falta el estado mensual de octubre en Noetinger",
            "Hitos vencidos en Noetinger",
        ]


def test_an_address_in_the_list_whose_account_turned_a_kind_off_does_not_get_it(client):
    noetinger = _municipality()
    configure(noetinger, ["admin@noetinger.test", "prensa@example.test"])
    _light(noetinger)
    _project(noetinger, _overdue())
    login(client, "admin@noetinger.test")
    client.put("/api/auth/notifications/milestone_overdue", json={"enabled": False})

    notifications.notify(TODAY)

    assert emails_to("admin@noetinger.test") == []
    assert len(emails_to("prensa@example.test")) == 1


def test_an_address_is_not_told_twice_when_the_list_changes(client):
    noetinger = _municipality()
    _light(noetinger)
    _project(noetinger, _overdue())
    notifications.notify(TODAY)  # the administrator hears about it

    configure(noetinger, ["admin@noetinger.test", "prensa@example.test"])
    notifications.notify(TODAY)

    assert len(emails_to("admin@noetinger.test")) == 1
    assert len(emails_to("prensa@example.test")) == 1


def test_notifications_use_the_municipality_s_own_text(client):
    noetinger = _municipality()
    _light(noetinger)
    _project(noetinger, _overdue())
    login(client, "admin@noetinger.test")
    client.put(
        "/api/admin/email-templates/milestone_overdue",
        json={
            "subject": "Atención {{municipality}}: hitos atrasados",
            "html": "<p>Revisen esto:</p>{{items}}",
        },
    )

    notifications.notify(TODAY)

    [email] = emails_to("admin@noetinger.test")
    assert email.subject == "Atención Noetinger: hitos atrasados"
    assert email.body.startswith("Revisen esto:\n\n• Pavimentación")


def test_a_run_reports_how_many_municipalities_and_emails(client):
    noetinger = _municipality()
    _light(noetinger)
    _project(noetinger, _overdue(), _overdue(days=9))
    saira = _municipality("Saira", "admin@saira.test")
    _light(saira)
    _project(saira, _overdue())
    make_membership(make_user("jefa@saira.test"), saira, admin=True, enable=["projects"])
    _municipality("Tortugas", "admin@tortugas.test")

    report = notifications.notify(TODAY)

    # Noetinger: one email for its admin; Saira: one for each of its two admins; Tortugas:
    # its missing light.
    assert (report.municipalities, report.emails) == (3, 4)
    assert notifications.notify(TODAY).emails == 0


def test_overdue_milestones_are_listed_by_date_then_project_then_name(client):
    noetinger = _municipality()
    _light(noetinger)
    term = make_term(noetinger)
    axis, department = make_axis(noetinger, term), make_department(noetinger)
    early, late = TODAY - timedelta(days=20), TODAY - timedelta(days=5)
    make_project(noetinger, term, axis, department, name="Plaza", milestones=[(late, None)])
    make_project(
        noetinger,
        term,
        axis,
        department,
        name="Cloacas",
        milestones=[(late, None), (late, None), (early, None), (early, TODAY)],
    )

    notifications.notify(TODAY)

    [email] = emails_to("admin@noetinger.test")
    lines = [line for line in email.body.splitlines() if line.startswith("• ")]
    assert [line.split("«")[1].split("»")[0] for line in lines] == [
        "Hito 3",
        "Hito 1",
        "Hito 2",
        "Hito 1",
    ]
    assert [line.split(" (")[0] for line in lines] == [
        "• Cloacas",
        "• Cloacas",
        "• Cloacas",
        "• Plaza",
    ]
