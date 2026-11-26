"""Residents learn how their complaints end, and nothing of what employees wrote to each other."""

import json
from datetime import datetime

import pytest
from sqlalchemy import select

from gobernar360.platform import notice_delivery
from gobernar360.platform.models import AuditLog, EmailOutbox, Municipality
from gobernar360.platform.resident_notice_models import ResidentNotice
from tests.complaints.factories import (
    BASE,
    Setup,
    complaints_member,
    make_person,
    signed_in,
)
from tests.factories import admin_session, emails_to, login
from tests.platform.notices import (  # noqa: F401
    CUIL,
    fake_cidi,
    make_resident,
    notices,
    outcomes,
    use_channel,
)

ADDRESS = "lucia@example.test"
MARKER = "NOTA-INTERNA-7391"


def _move(client, complaint, to_state="resolved", **body):
    return client.post(
        f"{BASE}/complaints/{complaint.id}/transitions", json={"to_state": to_state} | body
    )


def _municipality_of(complaint) -> Municipality:
    with admin_session() as session:
        return session.get(Municipality, complaint.municipality_id)


def _detail(client, complaint) -> dict:
    return client.get(f"{BASE}/complaints/{complaint.id}").json()


@pytest.fixture
def case(client, fake_cidi):  # noqa: F811
    """A complaint being worked on, of a resident with an account and an address, in a
    municipality that uses CiDi."""
    municipality = signed_in(client)
    use_channel(municipality, "cidi_then_email")
    person = make_resident(municipality, CUIL, ADDRESS)
    return Setup(municipality).complaint("in_progress", person=person)


def test_resolving_a_complaint_tells_its_resident_through_cidi(client, case, fake_cidi):  # noqa: F811
    resolved = _move(client, case, message_to_resident=" Ya funciona.\nGracias por avisar. ")

    assert resolved.status_code == 201
    [notice] = notices()
    assert (notice.channel, notice.state, notice.kind) == ("cidi", "queued", "complaint_resolved")
    event = resolved.json()["timeline"][-1]
    assert notice.event_key == f"complaint:{case.id}:resolved:{event['id']}"
    assert (notice.subject_dashboard, notice.subject_kind, notice.subject_ref) == (
        "complaints",
        "complaint",
        str(case.id),
    )
    notice_delivery.deliver()
    [sent] = fake_cidi.messages()
    assert sent == {
        "recipient_cuil": CUIL,
        "subject": f"Tu reclamo {case.number} fue resuelto",
        "body": f"Hola, Lucía Fernández:\n\nNoetinger resolvió tu reclamo {case.number} "
        "(Luminaria apagada).\n\nYa funciona.\nGracias por avisar.\n\n—\nNoetinger\n"
        "Este mensaje se envió automáticamente; no hace falta responderlo.\n",
        "reference": str(notice.id),
    }
    assert (sent["subject"], sent["body"]) == (notice.title, notice.body)
    assert outcomes() == [("cidi", "handed_over")]
    assert emails_to(ADDRESS) == []


def test_rejecting_one_tells_it_too(client, case):
    _move(client, case, "rejected", note="Fuera de la jurisdicción")

    [notice] = notices()
    assert (notice.kind, notice.title) == (
        "complaint_rejected",
        f"Novedades de tu reclamo {case.number}",
    )


def test_the_other_moves_tell_nothing(client, case):
    for to_state in ("waiting", "in_progress"):
        _move(client, case, to_state)
    assert notices() == []

    _move(client, case, "resolved")
    _move(client, case, "closed")

    assert len(notices()) == 1


def test_what_employees_write_to_each_other_never_leaves(client, case, fake_cidi):  # noqa: F811
    """Not the note of the move, nor any other of the timeline, nor the description."""
    client.post(f"{BASE}/complaints/{case.id}/comments", json={"note": f"{MARKER}-1"})
    client.patch(f"{BASE}/complaints/{case.id}", json={"description": f"{MARKER}-2"})
    _move(client, case, "waiting", note=f"{MARKER}-3")
    _move(client, case, "in_progress")
    _move(client, case, "resolved", note=f"{MARKER}-4", message_to_resident="Listo")
    _move(client, case, "reopened", note=f"{MARKER}-5")
    fake_cidi.path.touch()
    notice_delivery.deliver()
    _move(client, case, "rejected", note=f"{MARKER}-6")
    with admin_session() as session, session.begin():
        for notice in session.scalars(select(ResidentNotice)):
            assert MARKER not in notice.title + notice.body
    notice_delivery.deliver()

    assert len(notices()) == 2 and len(fake_cidi.messages()) == 2
    assert MARKER not in json.dumps(fake_cidi.messages())
    with admin_session() as session:
        emails = session.scalars(select(EmailOutbox)).all()
        assert emails == []
        audited = [
            entry.changes
            for entry in session.scalars(select(AuditLog))
            if entry.entity_type == "resident_notices"
        ]
    assert len(audited) == 2 and MARKER not in json.dumps(audited)
    assert MARKER in json.dumps(_detail(client, case)["timeline"])


def test_nor_does_it_by_email(client):
    municipality = signed_in(client)
    person = make_resident(municipality, email=ADDRESS)
    complaint = Setup(municipality).complaint("in_progress", person=person)

    _move(client, complaint, note=MARKER, message_to_resident="Listo")

    [email] = emails_to(ADDRESS)
    assert "Listo" in email.body and "Listo" in email.body_html
    assert MARKER not in email.subject + email.body + email.body_html
    assert outcomes() == [("email", "handed_over")]


def test_the_message_is_not_kept_in_the_timeline(client, case):
    _move(client, case, note="Interna", message_to_resident="Para el vecino")

    detail = _detail(client, case)

    assert detail["timeline"][-1]["note"] == "Interna"
    assert "Para el vecino" not in json.dumps(detail)


def test_a_resident_with_nothing_to_be_told_by_is_shown_to_the_editor(client):
    municipality = signed_in(client)
    complaint = Setup(municipality).complaint("in_progress", person=make_person(municipality))

    _move(client, complaint)

    [notice] = _detail(client, complaint)["notices"]
    assert (notice["state"], notice["handed_over_at"]) == ("no_channel", None)


def test_an_anonymous_complaint_tells_nobody(client):
    municipality = signed_in(client)
    complaint = Setup(municipality).complaint("in_progress")

    assert _move(client, complaint).status_code == 201

    assert notices() == []
    assert _detail(client, complaint)["notices"] == []


def test_a_message_needs_somebody_to_read_it(client, case):
    anonymous = Setup(_municipality_of(case)).complaint("in_progress")
    refused = (422, "There is nobody to send that message to.")

    def answer(response):
        return response.status_code, response.json()["error"]["message"]

    assert answer(_move(client, anonymous, message_to_resident="Hola")) == refused
    assert answer(_move(client, case, "waiting", message_to_resident="Hola")) == refused
    assert notices() == [] and _detail(client, case)["state"] == "in_progress"


def test_a_message_has_a_length(client, case):
    assert _move(client, case, message_to_resident="x" * 501).status_code == 422
    assert _move(client, case, message_to_resident="x" * 500).status_code == 201
    assert "x" * 500 in notices()[0].body


def test_a_move_that_is_not_allowed_tells_nothing(client, case):
    assert _move(client, case, "closed").status_code == 409
    assert _move(client, case, "rejected").status_code == 422

    assert notices() == []


def test_a_complaint_solved_twice_is_told_twice(client, case):
    _move(client, case)
    _move(client, case, "reopened", note="Volvió a fallar")
    _move(client, case)

    first, second = notices()
    assert first.event_key != second.event_key


def test_editors_see_how_each_notice_went_and_not_what_it_said(client, case):
    _move(client, case, message_to_resident="Secreto del vecino")
    queued = _detail(client, case)["notices"]
    notice_delivery.deliver()
    [shown] = _detail(client, case)["notices"]

    assert set(shown) == {"id", "kind", "channel", "state", "created_at", "handed_over_at"}
    assert [(n["channel"], n["state"], n["handed_over_at"]) for n in queued] == [
        ("cidi", "queued", None)
    ]
    assert (shown["kind"], shown["channel"], shown["state"]) == (
        "complaint_resolved",
        "cidi",
        "handed_over",
    )
    assert datetime.fromisoformat(shown["handed_over_at"]).tzinfo is not None
    assert "Secreto" not in json.dumps(_detail(client, case))


def test_viewers_never_receive_them(client, case):
    _move(client, case)
    complaints_member("viewer", "leo@noetinger.test", _municipality_of(case))
    complaints_member("admin", "jefa@noetinger.test", _municipality_of(case))
    client.post("/api/auth/logout")
    login(client, "leo@noetinger.test")

    assert _detail(client, case)["notices"] is None
    client.post("/api/auth/logout")
    login(client, "jefa@noetinger.test")
    assert len(_detail(client, case)["notices"]) == 1


def test_another_municipality_sees_nothing_of_it(client, case):
    _move(client, case)
    complaints_member("admin", "admin@saira.test", municipality_name="Saira")
    client.post("/api/auth/logout")
    login(client, "admin@saira.test")

    assert client.get(f"{BASE}/complaints/{case.id}").status_code == 404


def test_a_resident_is_found_by_exact_cuil_and_added_with_one(client):
    municipality = signed_in(client)
    setup = Setup(municipality)
    person = make_resident(municipality, CUIL)
    lookup = f"{BASE}/people/lookup"

    found = client.get(lookup, params={"cuil": "20-12345678-6"}).json()["person"]
    assert (found["id"], found["cuil"]) == (str(person.id), CUIL)
    assert client.get(lookup, params={"cuil": "27111111117"}).json()["person"] is None
    for params in ({}, {"cuil": "20-12345678-7"}, {"cuil": CUIL, "dni": "12345678"}):
        assert client.get(lookup, params=params).status_code == 422

    body = {
        "type_id": str(setup.type.id),
        "zone_id": str(setup.zone.id),
        "address": "San Martín 1",
    }
    new = {"first_name": "Rosa", "last_name": "Aguirre", "cuil": "27-11111111-7"}
    created = client.post(f"{BASE}/complaints", json=body | {"new_person": new})
    assert created.status_code == 201, created.text
    found = client.get(lookup, params={"cuil": "27111111117"}).json()["person"]
    assert found["full_name"] == "Aguirre, Rosa"
    repeated = client.post(f"{BASE}/complaints", json=body | {"new_person": new})
    assert (repeated.status_code, repeated.json()["error"]["code"]) == (409, "cuil_exists")


def test_the_detail_of_a_complaint_does_not_show_the_cuil(client, case):
    assert CUIL not in json.dumps(_detail(client, case))
