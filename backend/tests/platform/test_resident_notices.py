"""Notices to residents: the channel of each, once per event, and handing them over."""

import logging
import threading
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import APIRouter
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from typer.testing import CliRunner

from gobernar360 import cli
from gobernar360.core.config import get_settings
from gobernar360.core.db import tenant_session
from gobernar360.core.errors import ApiError
from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import DashboardModule
from gobernar360.platform import cidi, notice_delivery, resident_notices
from gobernar360.platform.access import RequestContext, system_context
from gobernar360.platform.cidi import CidiNotConfigured, connection
from gobernar360.platform.cidi.fake import FakeCidi
from gobernar360.platform.cidi.ports import RecipientUnknown, Unavailable
from gobernar360.platform.models import (
    AuditLog,
    EmailOutbox,
    EmailTemplate,
    Municipality,
    Person,
)
from gobernar360.platform.resident_notice_models import CidiConnectionValue, ResidentNotice
from gobernar360.platform.subjects import Subject
from tests.factories import admin_session, emails_to, make_municipality, make_user
from tests.platform.notices import (  # noqa: F401
    CUIL,
    OTHER_CUIL,
    fake_cidi,
    make_resident,
    notices,
    outcomes,
    secrets_key,
    use_channel,
)

KIND = "demo_done"
SUBJECT = Subject("demo", "thing", "t-1")
ADDRESS = "lucia@example.test"
# Far ahead of the real clock: a queued notice becomes due at the database's now().
NOW = datetime(2100, 1, 4, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def demo_module():
    """A dashboard known only to the tests, which tells residents things."""
    registry.register(
        DashboardModule(
            key="demo",
            router=APIRouter(),
            get_summary=lambda ctx, day: [],
            notice_kinds=(KIND, KIND),
        )
    )
    yield
    registry.unregister("demo")


@pytest.fixture
def fake(monkeypatch, fake_cidi):  # noqa: F811
    """The fake CiDi of the installation, in memory."""
    fake = FakeCidi()
    monkeypatch.setattr(cidi, "fake_inbox", lambda: fake)
    return fake


def _municipality(channel="cidi_then_email", name="Noetinger"):
    municipality = make_municipality(name)
    use_channel(municipality, channel)
    _template(municipality)
    return municipality


def _template(municipality, html=None, subject="Caso {{code}} en {{municipality}}"):
    html = html or "<p>Hola, {{name}}:</p><p>Caso {{code}}, {{type}}.</p><p>{{message}}</p>"
    with admin_session() as session, session.begin():
        session.add(
            EmailTemplate(
                municipality_id=municipality.id, key=f"notice.{KIND}", subject=subject, html=html
            )
        )


@contextmanager
def _context(municipality, user=None):
    with tenant_session(municipality.id) as db:
        if user is None:
            yield system_context(db, municipality.id)
        else:
            yield RequestContext(user, municipality.id, None, db)


def _queue(municipality, person, event="demo:1", message=None, **params):
    with _context(municipality) as ctx:
        return resident_notices.queue(
            ctx, person, KIND, event, SUBJECT, message, **({"code": 7, "type": "Poda"} | params)
        )


def _deliver(**options):
    return notice_delivery.deliver(**options)


def _counts(report) -> tuple[int, int, int, int]:
    return report.handed_over, report.retrying, report.failed, report.emailed


# Which channel


@pytest.mark.parametrize(
    ("policy", "cuil", "email", "expected"),
    [
        ("cidi_then_email", CUIL, ADDRESS, ("cidi", "queued")),
        ("cidi_then_email", CUIL, "", ("cidi", "queued")),
        ("cidi_then_email", None, ADDRESS, ("email", "handed_over")),
        ("cidi_then_email", None, "", ("email", "no_channel")),
        ("cidi", CUIL, ADDRESS, ("cidi", "queued")),
        ("cidi", None, ADDRESS, ("cidi", "no_channel")),
        ("email", CUIL, ADDRESS, ("email", "handed_over")),
        ("email", CUIL, "", ("email", "no_channel")),
        # What was typed as an address may not be one.
        ("email", None, "no tiene", ("email", "no_channel")),
    ],
)
def test_the_best_channel_the_person_has(fake, policy, cuil, email, expected):
    municipality = _municipality(policy)

    notice = _queue(municipality, make_resident(municipality, cuil, email))

    assert outcomes() == [expected]
    assert (notice.channel, notice.state) == expected
    assert (notice.handed_over_at is not None) == (expected[1] == "handed_over")
    assert len(emails_to(ADDRESS)) == (expected == ("email", "handed_over"))
    assert fake.sent == []


@pytest.mark.parametrize(
    ("policy", "email", "expected"),
    [
        ("cidi_then_email", ADDRESS, ("email", "handed_over")),
        ("cidi_then_email", "", ("email", "no_channel")),
        ("cidi", ADDRESS, ("cidi", "no_channel")),
    ],
)
@pytest.mark.parametrize("mode", ["off", "live"])
def test_an_installation_that_does_not_reach_cidi_queues_nothing_for_it(
    monkeypatch, mode, policy, email, expected
):
    monkeypatch.setattr(get_settings(), "cidi_mode", mode)
    municipality = _municipality(policy)

    _queue(municipality, make_resident(municipality, CUIL, email))

    assert outcomes() == [expected]


def test_a_municipality_that_chose_nothing_writes_emails(fake):
    municipality = make_municipality()
    _template(municipality)

    _queue(municipality, make_resident(municipality, CUIL, " Lucia@Example.TEST "))

    assert outcomes() == [("email", "handed_over")]
    assert len(emails_to(ADDRESS)) == 1


# What it says


def test_the_text_is_made_from_the_template_and_frozen(fake):
    municipality = _municipality()
    person = make_resident(municipality, CUIL)

    _queue(municipality, person, message="Pasó la <b>cuadrilla</b>.\nGracias & saludos.")
    with admin_session() as session, session.begin():
        session.execute(update(EmailTemplate).values(subject="Otro", html="<p>Otro</p>"))
        session.execute(update(Person).values(first_name="Otra"))
        session.execute(update(Municipality).values(name="Otra"))

    [notice] = notices()
    assert (notice.title, notice.body) == (
        "Caso 7 en Noetinger",
        "Hola, Lucía Fernández:\n\nCaso 7, Poda.\n\n"
        "Pasó la <b>cuadrilla</b>.\nGracias & saludos.\n",
    )
    assert (notice.kind, notice.event_key) == (KIND, "demo:1")
    assert (notice.subject_dashboard, notice.subject_kind, notice.subject_ref) == (
        "demo",
        "thing",
        "t-1",
    )
    _deliver()
    [sent] = fake.sent
    assert (sent.recipient_cuil, sent.subject, sent.body, sent.reference) == (
        CUIL,
        notice.title,
        notice.body,
        str(notice.id),
    )


def test_the_email_says_the_same_with_what_people_typed_escaped():
    municipality = _municipality("email")

    _queue(
        municipality,
        make_resident(municipality, email=ADDRESS, first="<b>Lucía</b>"),
        message="1 < 2\ny listo",
    )

    [email], [notice] = emails_to(ADDRESS), notices()
    assert (email.subject, email.body) == (notice.title, notice.body)
    assert "&lt;b&gt;Lucía&lt;/b&gt;" in email.body_html
    assert "1 &lt; 2<br>y listo" in email.body_html


def test_without_a_message_there_is_no_gap_for_it():
    municipality = _municipality("email")

    _queue(municipality, make_resident(municipality))

    assert notices()[0].body == "Hola, Lucía Fernández:\n\nCaso 7, Poda.\n"


@pytest.mark.parametrize(("message", "added"), [("Gracias", "\nGracias\n"), (None, "")])
def test_a_text_without_a_place_for_the_message_does_not_lose_it(message, added):
    municipality = make_municipality()
    _template(municipality, "<p>{{name}}: caso {{code}} en {{municipality}}.</p>")

    _queue(municipality, make_resident(municipality), message=message)

    assert notices()[0].body == f"Lucía Fernández: caso 7 en Noetinger.\n{added}"


def test_a_title_is_one_line_that_fits():
    municipality = make_municipality()
    _template(municipality, subject="{{code}} {{type}}")

    _queue(municipality, make_resident(municipality), code="1\n2", type="x" * 400)

    assert notices()[0].title == ("1 2 " + "x" * 400)[:300]


def test_a_kind_without_a_text_is_a_mistake_of_the_dashboard():
    municipality = make_municipality()
    person = make_resident(municipality)

    with pytest.raises(KeyError, match="email.templates.notice.demo_done"):
        _queue(municipality, person)


def test_the_default_texts_of_complaints_claim_no_legal_effect():
    municipality = make_municipality()
    person = make_resident(municipality, email=ADDRESS)
    with _context(municipality) as ctx:
        for kind in ("complaint_resolved", "complaint_rejected"):
            resident_notices.queue(
                ctx, person, kind, kind, SUBJECT, "Gracias.", code=1234, type="Poda"
            )

    # Both of one transaction, so of the same moment.
    rejected, resolved = sorted(emails_to(ADDRESS), key=lambda email: email.subject)
    assert (resolved.subject, resolved.body) == (
        "Tu reclamo 1234 fue resuelto",
        "Hola, Lucía Fernández:\n\nNoetinger resolvió tu reclamo 1234 (Poda).\n\nGracias.\n\n"
        "—\nNoetinger\nEste mensaje se envió automáticamente; no hace falta responderlo.\n",
    )
    assert rejected.subject == "Novedades de tu reclamo 1234"
    assert "revisó tu reclamo 1234 (Poda) y no le va a dar curso." in rejected.body


# Once per event


def test_the_same_event_is_told_once():
    municipality = _municipality("email")
    person = make_resident(municipality, email=ADDRESS)

    first, again = _queue(municipality, person), _queue(municipality, person)
    other = _queue(municipality, person, event="demo:2")

    assert first is not None and again is None and other is not None
    assert len(notices()) == len(emails_to(ADDRESS)) == 2


def test_the_same_event_is_told_once_even_if_the_channel_changed(fake):
    municipality = _municipality()
    person = make_resident(municipality, CUIL, ADDRESS)
    _queue(municipality, person)
    get_settings().cidi_mode = "off"

    assert _queue(municipality, person) is None
    assert outcomes() == [("cidi", "queued")]


def test_one_event_may_be_told_to_two_people():
    municipality = _municipality("email")

    for first in ("Lucía", "Diego"):
        _queue(municipality, make_resident(municipality, email=ADDRESS, first=first))

    assert len(notices()) == 2


def test_two_that_tell_the_same_event_at_once_tell_it_once():
    municipality = _municipality("email")
    person = make_resident(municipality, email=ADDRESS)
    ready, results = threading.Barrier(2), []

    def tell():
        with _context(municipality) as ctx:
            ready.wait(timeout=10)
            results.append(
                resident_notices.queue(ctx, person, KIND, "demo:1", SUBJECT, code=7, type="Poda")
            )

    threads = [threading.Thread(target=tell) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(result is None for result in results) == [False, True]
    assert len(notices()) == len(emails_to(ADDRESS)) == 1


def test_the_database_keeps_one_of_each():
    municipality = _municipality("email")
    person = make_resident(municipality)
    _queue(municipality, person)
    [notice] = notices()

    def copy(**changes):
        fields = {
            column.name: getattr(notice, column.name)
            for column in ResidentNotice.__table__.columns
            if column.name != "id"
        }
        with admin_session() as session, session.begin():
            session.add(ResidentNotice(**(fields | changes)))

    for changes in (
        {},
        {"event_key": "x", "channel": "sms"},
        {"event_key": "x", "state": "read"},
        # Handed over when, and only then.
        {"event_key": "x", "state": "handed_over"},
        {"event_key": "x", "handed_over_at": NOW},
    ):
        with pytest.raises(IntegrityError):
            copy(**changes)
    copy(channel="cidi")


def test_if_the_change_is_undone_nothing_was_told():
    municipality = _municipality("email")
    person = make_resident(municipality, email=ADDRESS)

    with pytest.raises(RuntimeError):
        with _context(municipality) as ctx:
            resident_notices.queue(ctx, person, KIND, "demo:1", SUBJECT, code=7, type="Poda")
            raise RuntimeError

    assert notices() == [] and emails_to(ADDRESS) == []


# Whose


def test_a_notice_is_of_the_municipality_that_tells_it_and_audited_without_its_text():
    municipality = _municipality("email")
    person = make_resident(municipality, email=ADDRESS)
    user = make_user()
    with _context(municipality, user) as ctx:
        resident_notices.queue(ctx, person, KIND, "demo:1", SUBJECT, "Secreto", code=7, type="Poda")

    [notice] = notices()
    assert (notice.municipality_id, notice.created_by, notice.updated_by) == (
        municipality.id,
        user.id,
        user.id,
    )
    with admin_session() as session:
        [entry] = session.scalars(select(AuditLog))
    assert (entry.entity_type, entry.action, entry.entity_id) == (
        "resident_notices",
        "create",
        str(notice.id),
    )
    assert entry.changes == {"kind": KIND, "channel": "email", "state": "handed_over"}


def test_a_notice_cannot_be_about_somebody_of_another_municipality():
    municipality = _municipality("email")
    theirs = make_resident(make_municipality("Saira"), email=ADDRESS)

    with pytest.raises(ApiError) as raised:
        _queue(municipality, theirs)

    assert (raised.value.code, raised.value.message) == (
        "invalid_reference",
        "person_id does not reference an existing record.",
    )
    assert notices() == []


def test_a_municipality_never_sees_the_notices_of_another():
    noetinger, saira = _municipality("email"), _municipality("email", "Saira")
    _queue(noetinger, make_resident(noetinger))

    with _context(saira) as ctx:
        assert resident_notices.about(ctx.db, SUBJECT) == []
        assert ctx.db.scalar(select(func.count()).select_from(ResidentNotice)) == 0
    with _context(noetinger) as ctx:
        assert len(resident_notices.about(ctx.db, SUBJECT)) == 1
        assert resident_notices.about(ctx.db, Subject("demo", "thing", "t-2")) == []
        assert resident_notices.about(ctx.db, Subject("demo", "other", "t-1")) == []
        assert resident_notices.about(ctx.db, Subject("other", "thing", "t-1")) == []


# Handing over


def test_what_is_queued_is_handed_over_once(fake):
    municipality = _municipality()
    _queue(municipality, make_resident(municipality, CUIL))

    first, second = _deliver(now=lambda: NOW), _deliver(now=lambda: NOW)

    assert (_counts(first), _counts(second)) == ((1, 0, 0, 0), (0, 0, 0, 0))
    [notice] = notices()
    assert (notice.state, notice.attempts, notice.last_error) == ("handed_over", 1, None)
    assert (notice.external_id, notice.handed_over_at) == (f"fake-{notice.id}", NOW)
    assert len(fake.sent) == 1


def test_notices_go_in_the_order_they_were_made(fake):
    municipality = _municipality()
    person = make_resident(municipality, CUIL)
    for number in range(3):
        _queue(municipality, person, event=f"demo:{number}", code=number)

    assert _counts(_deliver(now=lambda: NOW + timedelta(days=9))) == (3, 0, 0, 0)

    assert [message.subject for message in fake.sent] == [
        "Caso 0 en Noetinger",
        "Caso 1 en Noetinger",
        "Caso 2 en Noetinger",
    ]


def test_whoever_has_no_account_is_emailed_the_same_when_the_municipality_wants(fake, caplog):
    municipality = _municipality()
    fake.unknown.add(CUIL)
    _queue(municipality, make_resident(municipality, CUIL, ADDRESS), message="1 < 2\n\nListo")

    with caplog.at_level(logging.WARNING):
        report = _deliver()

    assert _counts(report) == (0, 0, 1, 1)
    failed, emailed = notices()
    assert outcomes() == [("cidi", "failed"), ("email", "handed_over")]
    assert failed.last_error == "RecipientUnknown: The fake CiDi has no such account."
    assert (failed.attempts, failed.external_id) == (1, None)
    assert (emailed.title, emailed.body, emailed.event_key, emailed.person_id) == (
        failed.title,
        failed.body,
        failed.event_key,
        failed.person_id,
    )
    [email] = emails_to(ADDRESS)
    assert (email.subject, email.body) == (failed.title, failed.body)
    assert "<p>1 &lt; 2</p>" in email.body_html or "1 &lt; 2<br>" in email.body_html
    assert [r.getMessage() for r in caplog.records] == [
        f"Notice {failed.id} has no account to go to."
    ]
    # Neither is tried again.
    assert _counts(_deliver(due_only=False)) == (0, 0, 0, 0)


@pytest.mark.parametrize(("policy", "email"), [("cidi", ADDRESS), ("cidi_then_email", "")])
def test_whoever_has_no_account_is_not_emailed_otherwise(fake, policy, email):
    municipality = _municipality(policy)
    fake.unknown.add(CUIL)
    _queue(municipality, make_resident(municipality, CUIL, email))

    assert _counts(_deliver()) == (0, 0, 1, 0)

    assert outcomes() == [("cidi", "failed")]
    with admin_session() as session:
        assert session.scalars(select(EmailOutbox)).all() == []


def test_somebody_who_lost_their_cuil_since_has_no_account_to_go_to(fake):
    municipality = _municipality()
    _queue(municipality, make_resident(municipality, CUIL, ADDRESS))
    with admin_session() as session, session.begin():
        session.execute(update(Person).values(cuil=None))

    assert _counts(_deliver()) == (0, 0, 1, 1)

    assert notices()[0].last_error == "RecipientUnknown: The person no longer has a CUIL."


def test_a_fall_back_that_was_already_made_is_not_made_twice(fake):
    municipality = _municipality()
    person = make_resident(municipality, CUIL, ADDRESS)
    _queue(municipality, person)
    with _context(municipality) as ctx:
        notice = ctx.db.scalars(select(ResidentNotice)).one()
        assert resident_notices.fall_back(ctx, notice, person) is True
        assert resident_notices.fall_back(ctx, notice, person) is False

    assert len(emails_to(ADDRESS)) == 1


def test_while_cidi_is_down_it_is_tried_again_later_and_later_until_it_is_not(fake, caplog):
    municipality = _municipality()
    fake.unavailable = True
    _queue(municipality, make_resident(municipality, CUIL, ADDRESS))
    moment = datetime.now(UTC) + timedelta(seconds=1)
    delays = []

    for attempt in range(1, 21):
        report = _deliver(now=lambda: moment)  # noqa: B023
        [notice] = notices()
        assert notice.attempts == attempt
        assert notice.last_error == "Unavailable: The fake CiDi is unavailable."
        if attempt < 20:
            assert _counts(report) == (0, 1, 0, 0) and notice.state == "queued"
            delays.append(notice.next_attempt_at - moment)
            # Not a moment before.
            early = moment + delays[-1] - timedelta(seconds=1)
            assert _deliver(now=lambda: early).attempted == 0  # noqa: B023
            moment += delays[-1]

    assert _counts(report) == (0, 0, 1, 0) and notice.state == "failed"
    assert delays[:3] == [timedelta(seconds=30), timedelta(seconds=60), timedelta(seconds=120)]
    assert delays == sorted(delays) and delays[-1] == timedelta(hours=1)
    # Somebody without an account is one thing and CiDi being down is another.
    assert emails_to(ADDRESS) == []
    assert caplog.records[0].getMessage() == (
        f"Notice {notice.id} not handed over (attempt 1): "
        "Unavailable: The fake CiDi is unavailable."
    )


def test_when_cidi_is_down_the_rest_waits_for_the_next_run(fake):
    municipality = _municipality()
    fake.unavailable = True
    person = make_resident(municipality, CUIL)
    for number in range(3):
        _queue(municipality, person, event=f"demo:{number}")

    assert _counts(_deliver(due_only=False)) == (0, 1, 0, 0)

    assert [notice.attempts for notice in notices()] == [1, 0, 0]


def test_run_by_hand_it_also_tries_what_waits_for_a_retry(fake):
    municipality = _municipality()
    fake.unavailable = True
    _queue(municipality, make_resident(municipality, CUIL))
    _deliver()
    fake.unavailable = False

    assert _deliver().attempted == 0
    assert _counts(_deliver(due_only=False)) == (1, 0, 0, 0)


def test_an_error_nobody_foresaw_is_retried_without_its_text(monkeypatch, fake, caplog):
    municipality = _municipality()
    person = make_resident(municipality, CUIL)
    other = make_resident(municipality, OTHER_CUIL)
    _queue(municipality, person, event="demo:1")
    _queue(municipality, other, event="demo:2")
    send = fake.send

    def sometimes(communication):
        if communication.recipient_cuil == CUIL:
            raise RuntimeError("refused token=abc123")
        return send(communication)

    monkeypatch.setattr(fake, "send", sometimes)

    with caplog.at_level(logging.DEBUG):
        report = _deliver()

    # One that fails for reasons of its own does not stop the others.
    assert _counts(report) == (1, 1, 0, 0)
    assert [notice.last_error for notice in notices()] == ["RuntimeError", None]
    assert "abc123" not in caplog.text


def test_an_external_id_of_any_length_is_kept(monkeypatch, fake):
    municipality = _municipality()
    _queue(municipality, make_resident(municipality, CUIL))
    receipt = fake.send

    def long(communication):
        found = receipt(communication)
        return type(found)("x" * 300, found.accepted_at)

    monkeypatch.setattr(fake, "send", long)
    _deliver()

    assert notices()[0].external_id == "x" * 200


def test_the_notices_of_a_suspended_municipality_are_not_delivered(fake):
    suspended, other = _municipality(), _municipality(name="Saira")
    for municipality in (suspended, other):
        _queue(municipality, make_resident(municipality, CUIL), event=f"demo:{municipality.id}")
    with admin_session() as session, session.begin():
        session.get(Municipality, suspended.id).suspended_at = NOW

    assert _counts(_deliver()) == (1, 0, 0, 0)

    states = {notice.municipality_id: notice.state for notice in notices()}
    assert states == {suspended.id: "queued", other.id: "handed_over"}


def test_two_workers_never_hand_over_the_same_notice(fake):
    municipality = _municipality()
    _queue(municipality, make_resident(municipality, CUIL))

    with tenant_session(municipality.id) as db:
        assert notice_delivery._next(db, set(), None) is not None
        # Somebody else is at it: skipped, not waited for.
        assert _deliver(due_only=False).attempted == 0
    assert _counts(_deliver()) == (1, 0, 0, 0)


def test_with_cidi_off_nothing_is_delivered_and_it_is_said(fake):
    municipality = _municipality()
    _queue(municipality, make_resident(municipality, CUIL))
    get_settings().cidi_mode = "off"

    assert _deliver() is None
    result = CliRunner().invoke(cli.app, ["send-notices"])

    assert (result.exit_code, result.output) == (
        0,
        "CiDi is off (GOBERNAR360_CIDI_MODE): nothing is sent through it.\n",
    )
    assert outcomes() == [("cidi", "queued")] and fake.sent == []


def test_the_live_mode_sends_nothing_and_says_what_it_waits_for(fake):
    municipality = _municipality()
    _queue(municipality, make_resident(municipality, CUIL))
    get_settings().cidi_mode = "live"

    with pytest.raises(CidiNotConfigured):
        _deliver()
    result = CliRunner().invoke(cli.app, ["send-notices"])

    assert result.exit_code == 1
    assert result.output.startswith("Nothing was sent. GOBERNAR360_CIDI_MODE is live, ")
    [notice] = notices()
    assert (notice.state, notice.attempts) == ("queued", 0)


# Each municipality's own connection


@pytest.fixture
def live(monkeypatch, secrets_key):  # noqa: F811
    """A real adapter, as phase B will have: built from each municipality's connection."""
    built: list = []

    def adapter(found):
        built.append(found)
        return FakeCidi()

    monkeypatch.setattr(get_settings(), "cidi_mode", "live")
    monkeypatch.setattr(cidi, "live_adapter", adapter)
    return built


def _connect(municipality, **secrets):
    with tenant_session(municipality.id) as db:
        for name, value in secrets.items():
            row = CidiConnectionValue(municipality_id=municipality.id, name=name)
            connection.set_secret(row, municipality.id, value, NOW)
            db.add(row)
        db.add(
            CidiConnectionValue(
                municipality_id=municipality.id,
                name="system_name",
                value=f"gobernar360 – {municipality.name}",
                set_at=NOW,
            )
        )


def test_each_municipality_is_connected_with_its_own(live):
    noetinger, saira = _municipality(), _municipality(name="Saira")
    for municipality, token in ((noetinger, "uno"), (saira, "dos")):
        _connect(municipality, token=token)
        _queue(municipality, make_resident(municipality, CUIL), event=f"demo:{municipality.id}")

    assert _counts(_deliver()) == (2, 0, 0, 0)

    assert [(c.municipality_id, c.values, c.secrets) for c in live] == [
        (noetinger.id, {"system_name": "gobernar360 – Noetinger"}, {"token": "uno"}),
        (saira.id, {"system_name": "gobernar360 – Saira"}, {"token": "dos"}),
    ]
    assert "uno" not in repr(live[0])


def test_a_connection_that_cannot_be_read_stops_only_its_municipality(live, caplog, monkeypatch):
    noetinger, saira = _municipality(), _municipality(name="Saira")
    for municipality in (noetinger, saira):
        _connect(municipality, token=municipality.name)
        _queue(municipality, make_resident(municipality, CUIL), event=f"demo:{municipality.id}")
    with admin_session() as session, session.begin():
        # A value copied from the other one.
        stolen = session.scalar(
            select(CidiConnectionValue.encrypted).where(
                CidiConnectionValue.municipality_id == saira.id,
                CidiConnectionValue.name == "token",
            )
        )
        session.execute(
            update(CidiConnectionValue)
            .where(
                CidiConnectionValue.municipality_id == noetinger.id,
                CidiConnectionValue.name == "token",
            )
            .values(encrypted=stolen)
        )

    result = CliRunner().invoke(cli.app, ["send-notices"])

    assert result.exit_code == 1
    assert result.output.splitlines()[-2:] == [
        "Handed over: 1. Will be retried: 0. Failed: 0 (0 emailed instead).",
        "1 municipalities have a connection that cannot be decrypted: check "
        "GOBERNAR360_SECRETS_KEY.",
    ]
    attempts = {n.municipality_id: (n.state, n.attempts) for n in notices()}
    assert attempts == {noetinger.id: ("queued", 0), saira.id: ("handed_over", 1)}
    assert (
        f"The CiDi connection of {noetinger.id} cannot be read: "
        "The secret belongs to somebody else." in caplog.text
    )


# The command


def test_the_command_says_how_it_went(fake):
    municipality = _municipality()
    fake.unknown.add(OTHER_CUIL)
    _queue(municipality, make_resident(municipality, CUIL), event="demo:1")
    good = CliRunner().invoke(cli.app, ["send-notices"])
    _queue(municipality, make_resident(municipality, OTHER_CUIL, ADDRESS), event="demo:2")
    bad = CliRunner().invoke(cli.app, ["send-notices"])
    nothing = CliRunner().invoke(cli.app, ["send-notices"])

    assert (good.exit_code, good.output) == (
        0,
        "Handed over: 1. Will be retried: 0. Failed: 0 (0 emailed instead).\n",
    )
    assert bad.exit_code == 1
    assert bad.output.splitlines()[-1] == (
        "Handed over: 0. Will be retried: 0. Failed: 1 (1 emailed instead)."
    )
    assert (nothing.exit_code, nothing.output) == (
        0,
        "Handed over: 0. Will be retried: 0. Failed: 0 (0 emailed instead).\n",
    )


def test_watching_it_delivers_as_they_come_until_stopped(fake, monkeypatch):
    municipality = _municipality()
    person = make_resident(municipality, CUIL)
    _queue(municipality, person, event="demo:1")
    waits = []

    def wait(seconds):
        waits.append(seconds)
        if len(waits) == 2:
            _queue(municipality, person, event="demo:2")
        if len(waits) == 3:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli.time, "sleep", wait)

    result = CliRunner().invoke(cli.app, ["send-notices", "--watch", "--interval", "5"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "Handed over: 1. Will be retried: 0. Failed: 0 (0 emailed instead).",
        "Delivering notices every 5 s. Ctrl+C stops.",
        "Handed over: 1. Will be retried: 0. Failed: 0 (0 emailed instead).",
        "Stopped.",
    ]
    assert waits == [5, 5, 5]


def test_the_ports_errors_are_what_delivery_tells_apart():
    # A notice may be retried or not depending on them.
    assert not issubclass(Unavailable, RecipientUnknown)
    assert not issubclass(RecipientUnknown, Unavailable)
