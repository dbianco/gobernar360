"""Small rules whose edges nothing else would notice moving."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from gobernar360.core.config import Settings
from gobernar360.core.db import tenant_session
from gobernar360.dashboards import registry
from gobernar360.platform import clock, email_templates, notifications, outbox, status
from gobernar360.platform.csv_export import csv_response, plain_number, safe_text
from gobernar360.platform.listing import every_word, get_paging
from gobernar360.platform.models import (
    AuditLog,
    DashboardStatus,
    EmailOutbox,
    EmailTemplate,
    NotificationSent,
    Person,
)
from gobernar360.platform.people import PersonIn
from gobernar360.platform.people import create_person as register
from tests.factories import (
    admin_session,
    configure,
    emails_to,
    login,
    make_membership,
    make_municipality,
    make_user,
)
from tests.social.factories import make_person

# The day, in Argentina


@pytest.mark.parametrize(
    ("instant", "day"),
    [
        (datetime(2026, 3, 1, 2, 59, tzinfo=UTC), date(2026, 2, 28)),
        (datetime(2026, 3, 1, 3, 0, tzinfo=UTC), date(2026, 3, 1)),
    ],
)
def test_the_day_changes_at_midnight_in_argentina(monkeypatch, instant, day):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(clock, "datetime", Frozen)

    assert clock.get_today() == day


# Links


@pytest.mark.parametrize("base", ["https://app.test", "https://app.test/", "https://app.testX/"])
def test_links_are_built_from_the_address_of_the_app(base):
    assert Settings(app_url=base).app_link("/login") == base.rstrip("/") + "/login"


# Dashboards


def test_a_dashboard_that_is_not_installed_can_be_removed_without_harm(demo_dashboard):
    registry.unregister("nothing")
    assert registry.get_module("demo") is not None
    registry.unregister("demo")
    assert registry.get_module("demo") is None


# Lists


def test_lists_start_at_the_beginning_fifty_at_a_time():
    assert vars(get_paging()) == {"limit": 50, "offset": 0}


@pytest.mark.parametrize(
    ("typed", "found"),
    [
        ("50%", ["Cien al 50%"]),
        ("_", ["Con_guion"]),
        ("\\", ["Barra\\"]),
        ("CIEN", ["Cien al 50%"]),
        # Numbers are only documents where there is a document to look in.
        ("123", []),
        ("", ["Barra\\", "Cien al 50%", "Con_guion"]),
    ],
)
def test_searches_take_wildcards_literally(typed, found):
    municipality = make_municipality()
    for name in ("Cien al 50%", "Con_guion", "Barra\\"):
        make_person(municipality, name, "X", dni=None)

    with tenant_session(municipality.id) as db:
        query = select(Person.first_name).where(*every_word(typed, Person.first_name))
        assert sorted(db.scalars(query)) == found


def test_numbers_are_also_documents_where_there_is_one():
    municipality = make_municipality()
    make_person(municipality, "Ana", "X", dni="20123456")
    make_person(municipality, "Local 123", "X", dni=None)

    def found(text):
        with tenant_session(municipality.id) as db:
            words = every_word(text, Person.first_name, document=Person.dni)
            return sorted(db.scalars(select(Person.first_name).where(*words)))

    assert found("123") == ["Ana", "Local 123"]
    assert found("20.123.456") == ["Ana"]
    assert found("ana 20") == ["Ana"]
    assert found("ana local") == []


# Files


@pytest.mark.parametrize(
    ("value", "text"),
    [(None, ""), ("", ""), (0, "0"), ("x", "x"), ("=x", "'=x"), ("-1", "'-1"), ("@x", "'@x")],
)
def test_cells_are_safe_to_open_in_a_spreadsheet(value, text):
    assert safe_text(value) == text


@pytest.mark.parametrize(
    ("value", "text"),
    [(None, ""), (Decimal("1.50"), "1.5"), (Decimal("100"), "100"), (Decimal("0.0001"), "0.0001")],
)
def test_numbers_are_written_plainly(value, text):
    assert plain_number(value) == text


def test_files_are_downloads_spreadsheets_read_as_utf_8():
    response = csv_response("a.csv", ("ñ",), [("á,b",)])

    assert response.body == b'\xef\xbb\xbf\xc3\xb1\r\n"\xc3\xa1,b"\r\n'
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == 'attachment; filename="a.csv"'


# Status lights


def _light(municipality, key, year, month, color="green"):
    with admin_session() as session, session.begin():
        session.add(
            DashboardStatus(
                municipality_id=municipality.id,
                dashboard_key=key,
                year=year,
                month=month,
                color=color,
            )
        )


def test_each_light_is_of_one_dashboard_year_and_month():
    municipality = make_municipality()
    for key, year, month, color in (
        ("a", 2025, 3, "red"),
        ("b", 2026, 3, "yellow"),
        ("a", 2026, 4, "yellow"),
        ("a", 2026, 3, "green"),
        ("a", 2026, 1, "red"),
    ):
        _light(municipality, key, year, month, color)

    with tenant_session(municipality.id) as db:
        assert status.find(db, "a", 2026, 3).color == "green"
        assert status.find(db, "a", 2025, 3).color == "red"
        assert status.find(db, "b", 2026, 3).color == "yellow"
        assert status.find(db, "b", 2026, 4) is None
        assert [row.month for row in status.for_year(db, "a", 2026)] == [1, 3, 4]


def test_recent_lights_are_the_latest_and_the_five_months_before_it():
    municipality = make_municipality()
    for year, month in ((2026, 2), (2025, 12), (2025, 9), (2025, 8), (2026, 1), (2026, 3)):
        _light(municipality, "a", year, month)

    def recent(today, **options):
        with tenant_session(municipality.id) as db:
            return [(r.year, r.month) for r in status.recent(db, "a", today, **options)]

    assert recent(date(2026, 2, 1)) == [(2026, 2), (2026, 1), (2025, 12), (2025, 9)]
    assert recent(date(2026, 1, 31)) == [(2026, 1), (2025, 12), (2025, 9), (2025, 8)]
    assert recent(date(2026, 2, 28), previous=1) == [(2026, 2), (2026, 1)]
    assert recent(date(2025, 7, 31)) == []


@pytest.mark.parametrize(
    ("year", "month", "future"),
    [(2026, 2, False), (2026, 3, True), (2025, 12, False), (2027, 1, True), (2025, 3, False)],
)
def test_a_month_that_has_not_started_is_in_the_future(year, month, future):
    assert status.is_future(year, month, date(2026, 2, 28)) is future


# Email texts: tables without row-level security, so the municipality is always asked for


def test_a_municipality_never_uses_nor_changes_the_texts_of_another(client):
    noetinger, saira = make_municipality(), make_municipality("Saira")
    make_membership(make_user("admin@noetinger.test"), noetinger, admin=True)
    with admin_session() as session, session.begin():
        for key in ("invitation", "password_reset"):
            session.add(
                EmailTemplate(
                    municipality_id=saira.id, key=key, subject=f"De Saira: {key}", html="{{link}}"
                )
            )
    login(client, "admin@noetinger.test")
    path = "/api/admin/email-templates/invitation"
    body = {"subject": "De Noetinger", "html": "<p>{{link}}</p>"}

    listed = client.get("/api/admin/email-templates").json()
    restored = client.delete(path).json()
    saved = client.put(path, json=body).json()

    assert not any(row["customized"] or "Saira" in row["subject"] for row in listed)
    assert restored["customized"] is False
    assert (saved["key"], saved["subject"], saved["customized"]) == (
        "invitation",
        "De Noetinger",
        True,
    )
    with admin_session() as session:
        theirs = session.scalars(
            select(EmailTemplate.subject)
            .where(EmailTemplate.municipality_id == saira.id)
            .order_by(EmailTemplate.key)
        ).all()
    assert theirs == ["De Saira: invitation", "De Saira: password_reset"]


def test_each_email_has_its_own_text():
    municipality = make_municipality()
    with admin_session() as session, session.begin():
        session.add(
            EmailTemplate(
                municipality_id=municipality.id, key="invitation", subject="S", html="<p>H</p>"
            )
        )

    with admin_session() as session:
        own = email_templates.load(session, municipality.id, "invitation")
        other = email_templates.load(session, municipality.id, "password_reset")
        nobody = email_templates.load(session, None, "invitation")

    assert own == email_templates.Template("invitation", "S", "<p>H</p>", True)
    assert other == email_templates.default("password_reset")
    assert nobody == email_templates.default("invitation")


@pytest.mark.parametrize(
    ("html", "clean"),
    [
        ('<a href="https://a.test" title="t">x</a>', '<a href="https://a.test" title="t">x</a>'),
        ('<a href="https://a.test" onclick="f()" class="c" id="i">x</a>', '<a href="https://a.test">x</a>'),
        ('<a href="javascript:f()">x</a>', "<a>x</a>"),
        ('<a href="mailto:a@b.test">x</a>', '<a href="mailto:a@b.test">x</a>'),
        ('<p style="color:red" onclick="f()" id="i">x</p>', "<p>x</p>"),
        ("<script>f()</script><p>x</p>", "<p>x</p>"),
        ('<img src="x" onerror="f()">', ""),
    ],
)  # fmt: skip
def test_texts_keep_formatting_and_links_and_nothing_else(html, clean):
    assert email_templates.sanitize(html) == clean


def test_values_cannot_break_out_of_an_attribute():
    filled = email_templates.fill('<a title="{{name}}">', {"name": "\"'><script>"}, escape=True)

    assert filled == '<a title="&quot;&#x27;&gt;&lt;script&gt;">'
    assert email_templates.fill("{{name}}", {"name": "<b>"}, escape=False) == "<b>"


# Administrators: memberships have no row-level security either


def test_the_administrators_of_other_municipalities_do_not_count(client):
    noetinger, saira = make_municipality(), make_municipality("Saira")
    membership = make_membership(make_user("ana@noetinger.test"), noetinger, admin=True)
    make_membership(make_user("otra@saira.test"), saira, admin=True)
    login(client, "ana@noetinger.test")

    removed = client.delete(f"/api/admin/users/{membership.id}")
    imported = client.post(
        "/api/admin/users/import",
        json={"csv": "email,nombre,administrador\nana@noetinger.test,Ana,no\n"},
    )

    for response in (removed, imported):
        assert response.status_code == 409
        assert response.json()["error"] == {
            "code": "conflict",
            "message": "The municipality must keep at least one administrator.",
        }


# Notifications


def test_a_light_of_another_year_does_not_stand_for_the_month_that_ended(client):
    municipality = make_municipality()
    make_membership(make_user("ana@noetinger.test"), municipality, admin=True, enable=["projects"])
    _light(municipality, "projects", 2025, 2)

    notifications.notify(date(2026, 3, 1))

    assert len(emails_to("ana@noetinger.test")) == 1
    with admin_session() as session:
        assert session.scalars(select(NotificationSent.event_key)).all() == ["projects:2026-02"]


def test_who_turned_a_notice_off_does_not_keep_it_from_the_rest(client):
    municipality = make_municipality()
    for email in ("ana@noetinger.test", "beto@noetinger.test"):
        make_membership(make_user(email), municipality, admin=True, enable=["projects"])
    configure(municipality, ["ana@noetinger.test", "beto@noetinger.test", "prensa@example.test"])
    login(client, "ana@noetinger.test")
    kinds = client.get("/api/auth/notifications").json()
    for kind in kinds:
        client.put(f"/api/auth/notifications/{kind['kind']}", json={"enabled": False})

    notifications.notify(date(2026, 3, 1))

    sent = [len(emails_to(a)) for a in (
        "ana@noetinger.test", "beto@noetinger.test", "prensa@example.test"
    )]  # fmt: skip
    assert sent == [0, 1, 1]


# Email


def test_messages_are_identified_by_the_domain_of_the_sender():
    row = EmailOutbox(
        to_address="a@example.test", subject="s", body="b",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )  # fmt: skip

    def identifier(sender):
        return outbox.build_message(row, sender)["Message-ID"]

    assert identifier("Muni <no-reply@noetinger.test>") == "<None@noetinger.test>"
    assert identifier('"a@b" <x@noetinger.test>') == "<None@noetinger.test>"
    # A sender without an address still gives a valid identifier.
    assert identifier("") == "<None@gobernar360>"


def test_emails_go_out_in_the_order_they_were_written():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with admin_session() as session, session.begin():
        for name, minutes in (("c", 3), ("a", 1), ("b", 2)):
            session.add(
                EmailOutbox(
                    to_address=f"{name}@example.test",
                    subject="s",
                    body="b",
                    created_at=start + timedelta(minutes=minutes),
                )
            )
    sent = []

    class Transport:
        def send(self, message):
            sent.append(message["To"])
            if message["To"].startswith(("a", "b")):
                raise outbox.PermanentFailure("no")

    report = outbox.deliver(Transport(), "x@y.test", due_only=False)

    assert sent == ["a@example.test", "b@example.test", "c@example.test"]
    assert (report.sent, report.failed, report.retrying, report.attempted) == (1, 2, 0, 3)


def test_failed_emails_queued_again_are_due_at_once():
    with admin_session() as session, session.begin():
        session.add(
            EmailOutbox(
                to_address="a@example.test",
                subject="s",
                body="b",
                status="failed",
                attempts=20,
                next_attempt_at=datetime(2099, 1, 1, tzinfo=UTC),
            )
        )

    assert outbox.requeue_failed() == 1

    with admin_session() as session:
        row = session.scalars(select(EmailOutbox)).one()
    assert (row.status, row.attempts) == ("pending", 0)
    assert abs(row.next_attempt_at - datetime.now(UTC)) < timedelta(minutes=1)


def test_an_invitation_says_when_its_link_expires(client):
    municipality = make_municipality()
    make_membership(make_user("admin@noetinger.test"), municipality, admin=True)
    login(client, "admin@noetinger.test")
    client.put(
        "/api/admin/email-templates/invitation",
        json={"subject": "S", "html": "<p>{{link}} vence {{expires}}</p>"},
    )

    client.post("/api/admin/users", json={"email": "n@noetinger.test", "full_name": "Nueva"})

    [email] = emails_to("n@noetinger.test")
    expected = datetime.now(clock.LOCAL_TIMEZONE) + timedelta(days=7)
    assert f"vence {expected:%d/%m/%Y}" in " ".join(email.body.split())


# People


@pytest.mark.parametrize("dni", ["12345", "1234567890", "12a456"])
def test_a_document_has_six_to_nine_digits(dni):
    with pytest.raises(ValueError, match="must have 6 to 9 digits"):
        PersonIn(first_name="Ana", last_name="Gómez", dni=dni)


def test_registering_a_person_is_audited_with_their_data():
    municipality = make_municipality()
    user = make_user("ana@noetinger.test")
    from gobernar360.platform.access import RequestContext

    with tenant_session(municipality.id) as db:
        ctx = RequestContext(user=user, municipality_id=municipality.id, membership=None, db=db)
        register(ctx, PersonIn(first_name="Ana", last_name="Gómez", dni="20123456"))
        db.flush()
        [entry] = db.scalars(select(AuditLog))
        assert (entry.changes["first_name"], entry.changes["dni"]) == ("Ana", "20123456")


def test_municipalities_are_notified_by_name(monkeypatch):
    for name in ("Saira", "Bell Ville", "Noetinger"):
        make_municipality(name)
    visited = []
    monkeypatch.setattr(
        notifications,
        "notify_municipality",
        lambda db, municipality, today: visited.append(municipality.name) or 0,
    )

    report = notifications.notify(date(2026, 3, 1))

    assert visited == ["Bell Ville", "Noetinger", "Saira"]
    assert report.municipalities == 3
