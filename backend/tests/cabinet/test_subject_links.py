"""What commitments and agenda items point at, and who may know what it is."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.cabinet.factories import (
    ALL,
    EMAIL,
    URL,
    as_member,
    cabinet_member,
    close,
    commit,
    error,
    make_light,
    make_simple_project,
    month_subject,
    pin_today,
    prepare,
    project_subject,
)
from tests.factories import admin_session, enable_dashboards
from tests.projects.factories import make_axis, make_department, make_project, make_term

RESTRICTED_PROJECT = {
    "access": "restricted",
    "kind": "project",
    "dashboard_key": "projects",
    "ref": None,
    "label": None,
    "path": None,
    "color": None,
}
NO_SUCH = {
    "code": "invalid_reference",
    "message": "subject does not reference an existing record.",
}


@pytest.fixture(autouse=True)
def pinned_today(client):
    pin_today(client)


def try_commit(client, item, owner, subject):
    return client.post(
        f"{URL}/items/{item['id']}/commitments",
        json={
            "description": "Certificar",
            "owner_id": str(owner.id),
            "due_date": "2026-03-20",
            "subject": subject,
        },
    )


def test_a_commitment_is_linked_to_a_project(client):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    project = make_simple_project(municipality, "Pavimentación")

    taken = commit(client, prepare(client)["items"][0], ana, subject=project_subject(project))

    assert taken["subject"] == {
        "access": "visible",
        "kind": "project",
        "dashboard_key": "projects",
        "ref": str(project.id),
        "label": "Pavimentación",
        "path": f"/d/projects/projects/{project.id}",
        "color": None,
    }


def test_a_commitment_cannot_link_to_another_municipality_s_project(client):
    other, _ = cabinet_member(
        client, email="beto@saira.test", municipality_name="Saira", others={"projects": "admin"}
    )
    theirs = make_simple_project(other, "Secreta")
    _, ana = cabinet_member(client, others={"projects": "admin"})
    meeting = prepare(client)
    item = meeting["items"][0]
    taken = commit(client, item, ana)
    subject = project_subject(theirs)

    for response in (
        try_commit(client, item, ana, subject),
        client.patch(f"{URL}/commitments/{taken['id']}", json={"subject": subject}),
        client.patch(f"{URL}/items/{item['id']}", json={"subject": subject}),
        client.post(
            f"{URL}/meetings/{meeting['id']}/items", json={"title": "x", "subject": subject}
        ),
    ):
        assert response.status_code == 422, response.request.url
        assert response.json()["error"] == NO_SUCH
    shown = client.get(f"{URL}/meetings/{meeting['id']}").json()
    assert shown["items"][0]["subject"] is None
    assert shown["items"][0]["commitments"][0]["subject"] is None


def test_links_must_exist_and_be_visible_and_both_failures_look_the_same(client):
    municipality, ana = cabinet_member(client, others={"environment": "viewer"})
    project = make_simple_project(municipality)
    item = prepare(client)["items"][0]

    for subject in (
        # Exists, but the member has no access to Projects.
        project_subject(project),
        month_subject("projects", "2026-02"),
        # Do not exist.
        {"dashboard_key": "projects", "kind": "milestone", "ref": str(project.id)},
        {"dashboard_key": "lottery", "kind": "month", "ref": "2026-02"},
        {"dashboard_key": "environment", "kind": "project", "ref": str(project.id)},
        month_subject("environment", "2026-13"),
        month_subject("environment", "2026-2"),
        month_subject("environment", "٢٠٢٦-02"),
        month_subject("environment", "0026-02"),
        # Has not started.
        month_subject("environment", "2026-04"),
    ):
        response = try_commit(client, item, ana, subject)
        assert response.status_code == 422, subject
        assert response.json()["error"] == NO_SUCH, subject
    ok = try_commit(client, item, ana, month_subject("environment", "2026-03"))
    assert ok.status_code == 201


@pytest.mark.parametrize("ref", ["not-an-id", "00000000-0000-0000-0000-000000000000"])
def test_a_project_that_does_not_exist_cannot_be_linked(client, ref):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    item = prepare(client)["items"][0]

    response = try_commit(
        client, item, ana, {"dashboard_key": "projects", "kind": "project", "ref": ref}
    )

    assert response.json()["error"] == NO_SUCH


def test_the_id_is_stored_as_the_record_has_it(client):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    project = make_simple_project(municipality)
    item = prepare(client)["items"][0]
    subject = project_subject(project) | {"ref": str(project.id).upper().replace("-", "")}

    assert try_commit(client, item, ana, subject).json()["subject"]["ref"] == str(project.id)


@pytest.mark.parametrize("missing", ["dashboard_key", "kind", "ref"])
def test_a_link_is_given_whole(client, missing):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    subject = project_subject(make_simple_project(municipality))
    del subject[missing]

    response = try_commit(client, prepare(client)["items"][0], ana, subject)

    assert error(response) == (422, "validation_error")


def test_a_member_without_projects_sees_the_commitment_but_not_the_project_s_name(client):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    project = make_simple_project(municipality, "Pavimentación reservada")
    meeting = prepare(client)
    client.patch(
        f"{URL}/items/{meeting['items'][0]['id']}", json={"subject": project_subject(project)}
    )
    taken = commit(client, meeting["items"][0], ana, subject=project_subject(project))
    client.post(f"{URL}/meetings/{meeting['id']}/close")
    cabinet_member(client, "viewer", "leo@noetinger.test", municipality)

    one = client.get(f"/api/commitments/{taken['id']}")
    assert one.json()["description"] == "Certificar la obra"
    assert one.json()["subject"] == RESTRICTED_PROJECT
    # Nor anywhere else the commitment is shown.
    for path in (
        f"/api/commitments/{taken['id']}",
        f"{URL}/commitments",
        f"{URL}/meetings/{meeting['id']}",
        f"{URL}/meetings/{meeting['id']}/minutes.html",
        f"{URL}/summary",
        f"{URL}/export/commitments.csv",
    ):
        body = client.get(path)
        assert body.status_code == 200, path
        assert "reservada" not in body.text, path
        assert str(project.id) not in body.text, path
    assert (
        "Un proyecto al que no tenés acceso"
        in client.get(f"{URL}/meetings/{meeting['id']}/minutes.html").text
    )
    assert "Un proyecto al que no tenés acceso" in client.get(f"{URL}/export/commitments.csv").text
    as_member(client)
    assert client.get(f"/api/commitments/{taken['id']}").json()["subject"]["label"] == (
        "Pavimentación reservada"
    )


def test_a_month_the_member_cannot_see_does_not_even_say_whose_it_is(client):
    municipality, ana = cabinet_member(client, others={"environment": "viewer"})
    make_light(municipality, "environment", 2026, 2, "red")
    item = prepare(client)["items"][0]
    taken = commit(client, item, ana, subject=month_subject("environment", "2026-02"))
    assert taken["subject"]["color"] == "red"
    cabinet_member(client, "viewer", "leo@noetinger.test", municipality)

    seen = client.get(f"/api/commitments/{taken['id']}").json()["subject"]

    assert seen == RESTRICTED_PROJECT | {"kind": "month", "dashboard_key": None}


def test_a_month_without_a_light_can_be_linked(client):
    _, ana = cabinet_member(client, others={"environment": "viewer"})
    item = prepare(client)["items"][0]

    taken = commit(client, item, ana, subject=month_subject("environment", "2026-01"))

    assert taken["subject"]["label"] == "Ambiental, enero de 2026"
    assert taken["subject"]["color"] is None


def test_a_deleted_project_reads_as_deleted_only_to_those_who_could_see_it(client):
    municipality, ana = cabinet_member(client, others={"projects": "editor"})
    project = make_simple_project(municipality)
    meeting = prepare(client)
    taken = commit(client, meeting["items"][0], ana, subject=project_subject(project))
    close(client, meeting)
    assert client.delete(f"/api/dashboards/projects/projects/{project.id}").status_code == 204

    seen = client.get(f"/api/commitments/{taken['id']}").json()["subject"]
    assert (seen["access"], seen["label"], seen["path"]) == ("deleted", None, None)
    assert "Un proyecto que ya no existe" in client.get(f"{URL}/export/commitments.csv").text
    cabinet_member(client, "viewer", "leo@noetinger.test", municipality)
    hidden = client.get(f"/api/commitments/{taken['id']}").json()["subject"]
    assert hidden == RESTRICTED_PROJECT


def test_a_dashboard_turned_off_takes_its_names_with_it(client):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    project = make_simple_project(municipality)
    taken = commit(client, prepare(client)["items"][0], ana, subject=project_subject(project))
    with admin_session() as session, session.begin():
        session.execute(
            text("DELETE FROM municipality_dashboards WHERE dashboard_key = 'projects'")
        )

    seen = client.get(f"/api/commitments/{taken['id']}").json()["subject"]

    assert seen == RESTRICTED_PROJECT
    enable_dashboards(municipality, list(ALL))


def test_an_editor_without_projects_keeps_the_link_it_cannot_read_or_removes_it(client):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    project = make_simple_project(municipality)
    taken = commit(client, prepare(client)["items"][0], ana, subject=project_subject(project))
    cabinet_member(client, "editor", "leo@noetinger.test", municipality)
    url = f"{URL}/commitments/{taken['id']}"

    assert client.patch(url, json={"description": "Otra"}).json()["subject"] == RESTRICTED_PROJECT
    as_member(client, EMAIL)
    shown = client.get(f"/api/commitments/{taken['id']}").json()
    assert shown["subject"]["ref"] == str(project.id)
    as_member(client, "leo@noetinger.test")
    assert client.patch(url, json={"subject": None}).json()["subject"] is None


def test_a_renamed_project_is_shown_with_its_new_name(client):
    municipality, ana = cabinet_member(client, others={"projects": "editor"})
    project = make_simple_project(municipality, "Antes")
    taken = commit(client, prepare(client)["items"][0], ana, subject=project_subject(project))
    client.patch(f"/api/dashboards/projects/projects/{project.id}", json={"name": "Después"})

    assert client.get(f"/api/commitments/{taken['id']}").json()["subject"]["label"] == "Después"


def test_the_database_refuses_half_a_link(client):
    _, ana = cabinet_member(client)
    taken = commit(client, prepare(client)["items"][0], ana)

    with pytest.raises(IntegrityError, match="subject_complete"):
        with admin_session() as session, session.begin():
            session.execute(
                text("UPDATE commitments SET subject_kind = 'project' WHERE id = :id"),
                {"id": taken["id"]},
            )


def test_many_links_of_one_kind_are_each_their_own(client):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    term = make_term(municipality)
    axis, department = make_axis(municipality, term), make_department(municipality)
    item = prepare(client)["items"][0]
    for name in ("Uno", "Dos"):
        project = make_project(municipality, term, axis, department, name=name)
        commit(client, item, ana, description=name, subject=project_subject(project))

    listed = client.get(f"{URL}/commitments").json()["items"]

    assert [(c["description"], c["subject"]["label"]) for c in listed] == [
        ("Uno", "Uno"),
        ("Dos", "Dos"),
    ]
