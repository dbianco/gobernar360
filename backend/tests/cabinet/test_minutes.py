from datetime import date, datetime

import pytest

from gobernar360.platform.texts import format_datetime
from tests.cabinet.factories import (
    URL,
    as_member,
    cabinet_member,
    close,
    commit,
    error,
    held,
    make_light,
    make_simple_project,
    month_subject,
    pin_today,
    prepare,
    project_subject,
)
from tests.factories import admin_session, make_membership, make_user

PROJECTS = "/api/dashboards/projects/projects"


@pytest.fixture(autouse=True)
def pinned_today(client):
    pin_today(client)


def minutes(client, meeting) -> str:
    response = client.get(f"{URL}/meetings/{meeting['id']}/minutes.html")
    assert response.status_code == 200, response.text
    return response.text


def test_the_minutes_hold_everything_the_meeting_recorded(client):
    municipality, ana = cabinet_member(
        client, others={"projects": "editor", "environment": "viewer"}
    )
    make_light(municipality, "environment", 2026, 2, "red")
    project = make_simple_project(municipality)
    held(client, ana, date(2026, 2, 20))
    meeting = prepare(
        client,
        agenda=[{"key": "light:environment:2026-02"}, "Feria"],
        attendee_ids=[str(ana.id)],
        guests="Ing. Funes",
    )
    light = meeting["items"][0]
    client.patch(f"{URL}/items/{light['id']}", json={"notes": "Se rompió la balanza."})
    commit(client, light, ana, subject=month_subject("environment", "2026-02"))
    commit(client, light, ana, description="Firmar", subject=project_subject(project))
    client.patch(f"{URL}/meetings/{meeting['id']}", json={"notes": "Cierre\ngeneral"})
    close(client, meeting)

    text = minutes(client, meeting)

    for piece in (
        "<title>Acta de la reunión de gabinete del 10/03/2026</title>",
        "<h1>Acta de la reunión de gabinete del 10/03/2026</h1>",
        '<p class="muted">Noetinger</p>',
        "<h2>Participantes</h2><p>Ana</p><p>También participaron: Ing. Funes</p>",
        "<h2>Temario</h2><h3>1. Ambiental, febrero de 2026 (crítico)</h3>"
        "<p>Se rompió la balanza.</p><p><strong>Compromisos</strong></p><ul>"
        '<li>Certificar la obra<br><span class="muted">Ana, para el 20/03/2026</span>'
        '<br><span class="muted">Sobre: Ambiental, febrero de 2026 (crítico)</span></li>'
        '<li>Firmar<br><span class="muted">Ana, para el 20/03/2026</span>'
        '<br><span class="muted">Sobre: Pavimentación</span></li></ul>',
        '<h3>2. Feria</h3><p class="muted">No se trató en esta reunión.</p>',
        "<h2>Compromisos que venían de reuniones anteriores</h2><ul><li>Compromiso 1<br>"
        '<span class="muted">Ana, para el 20/02/2026 · vencido, postergado una vez</span></li>',
        "<h2>Notas generales</h2><p>Cierre\ngeneral</p>",
        '<hr><p class="muted">Reunión cerrada por Ana el ',
    ):
        assert piece in text


def test_items_say_what_they_are_about_and_everyone_who_came_is_named(client):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    project = make_simple_project(municipality)
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)
    held(client, ana, date(2026, 2, 20), date(2026, 2, 21))
    meeting = prepare(client, agenda=[], attendee_ids=[str(leo.id), str(ana.id)])
    item = {"title": "Obra vial", "subject": project_subject(project)}
    client.post(f"{URL}/meetings/{meeting['id']}/items", json=item)
    closed = close(client, meeting)

    text = minutes(client, meeting)

    assert "<h2>Participantes</h2><p>Ana, Leo</p>" in text
    assert '<h3>1. Obra vial</h3><p class="muted">Sobre: Pavimentación</p>' in text
    assert "una vez</span></li><li>Compromiso 2<br>" in text
    when = format_datetime(datetime.fromisoformat(closed["closed_at"]))
    assert f"Reunión cerrada por Ana el {when}." in text
    # Nothing written, nothing printed.
    assert "<p></p>" not in text


def test_the_minutes_are_a_download(client):
    cabinet_member(client)
    meeting = prepare(client)
    close(client, meeting)

    response = client.get(f"{URL}/meetings/{meeting['id']}/minutes.html")

    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.headers["content-disposition"] == (
        'attachment; filename="acta-gabinete-2026-03-10.html"'
    )


def test_an_open_meeting_has_no_minutes(client):
    cabinet_member(client)
    meeting = prepare(client)

    response = client.get(f"{URL}/meetings/{meeting['id']}/minutes.html")

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "meeting_not_closed",
        "message": "The meeting has no minutes until it is closed.",
    }


def test_the_minutes_do_not_change_with_what_happens_later(client):
    municipality, ana = cabinet_member(
        client, others={"projects": "editor", "environment": "admin"}
    )
    make_light(municipality, "environment", 2026, 2, "red")
    project = make_simple_project(municipality, "Nombre de entonces")
    [late] = held(client, ana, date(2026, 2, 20))
    meeting = prepare(
        client,
        agenda=[{"key": "light:environment:2026-02"}, {"key": f"commitment:{late['id']}"}],
        attendee_ids=[str(ana.id)],
    )
    taken = commit(client, meeting["items"][0], ana, subject=project_subject(project))
    close(client, meeting)
    before = minutes(client, meeting)
    assert "Nombre de entonces" in before and "crítico" in before

    client.patch(f"{URL}/commitments/{taken['id']}", json={"due_date": "2027-01-01"})
    client.post(f"{URL}/commitments/{taken['id']}/state", json={"state": "done"})
    client.post(f"{URL}/commitments/{late['id']}/state", json={"state": "dropped"})
    client.post(f"{URL}/commitments/{taken['id']}/notes", json={"note": "Listo."})
    client.patch(f"{PROJECTS}/{project.id}", json={"name": "Nombre nuevo"})
    client.put("/api/dashboards/environment/status/2026/2", json={"color": "green"})
    with admin_session() as session, session.begin():
        session.merge(ana).full_name = "Ana Cambiada"
    prepare(client, date(2026, 3, 25))
    pin_today(client, date(2026, 6, 1))

    assert minutes(client, meeting) == before
    client.delete(f"{PROJECTS}/{project.id}")
    assert minutes(client, meeting) == before


def test_whoever_closes_it_the_minutes_name_links_only_to_those_who_may_see_them(client):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    project = make_simple_project(municipality)
    meeting = prepare(client)
    commit(client, meeting["items"][0], ana, subject=project_subject(project))
    # Closed by someone who cannot see the project.
    cabinet_member(client, "editor", "leo@noetinger.test", municipality)
    close(client, meeting)

    hidden = minutes(client, meeting)
    assert "Pavimentación" not in hidden
    assert "Sobre: Un proyecto al que no tenés acceso" in hidden
    as_member(client)
    assert "Sobre: Pavimentación" in minutes(client, meeting)


def test_a_light_s_title_is_hidden_from_members_without_the_dashboard(client):
    municipality, _ = cabinet_member(client, others={"environment": "viewer"})
    make_light(municipality, "environment", 2026, 2, "red")
    meeting = prepare(client, agenda=[{"key": "light:environment:2026-02"}])
    close(client, meeting)
    cabinet_member(client, "viewer", "leo@noetinger.test", municipality)

    text = minutes(client, meeting)

    assert "<h3>1. Un estado mensual de un tablero al que no tenés acceso</h3>" in text
    assert "Ambiental" not in text and "crítico" not in text


def test_what_people_typed_cannot_become_markup(client):
    _, ana = cabinet_member(client)
    attack = "<script>alert(1)</script>"
    meeting = prepare(client, agenda=[attack], guests=attack, attendee_ids=[str(ana.id)])
    item = meeting["items"][0]
    client.patch(f"{URL}/items/{item['id']}", json={"notes": attack})
    client.patch(f"{URL}/meetings/{meeting['id']}", json={"notes": attack})
    commit(client, item, ana, description=attack)
    close(client, meeting)

    text = minutes(client, meeting)

    assert "<script" not in text
    assert text.count("&lt;script&gt;alert(1)&lt;/script&gt;") == 5


def test_an_empty_meeting_says_so(client):
    cabinet_member(client)
    meeting = prepare(client, agenda=[])
    close(client, meeting)

    text = minutes(client, meeting)

    assert "<h2>Participantes</h2><p>Sin datos.</p><h2>Temario</h2><p>Sin datos.</p><hr>" in text


def test_a_commitment_postponed_twice_says_how_many_times(client):
    _, ana = cabinet_member(client)
    held(client, ana, date(2026, 9, 1))
    close(client, prepare(client, date(2026, 3, 1)))
    meeting = prepare(client)
    close(client, meeting)

    assert "pendiente, postergado 2 veces" in minutes(client, meeting)


def test_minutes_need_access_to_the_dashboard(client):
    municipality, _ = cabinet_member(client)
    meeting = prepare(client)
    close(client, meeting)
    cabinet_member(client, None, "leo@noetinger.test", municipality, {"projects": "admin"})

    assert error(client.get(f"{URL}/meetings/{meeting['id']}/minutes.html")) == (403, "forbidden")
