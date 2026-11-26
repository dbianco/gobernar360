import csv
import io
from datetime import date

import pytest

from tests.cabinet.factories import (
    URL,
    cabinet_member,
    commit,
    held,
    make_light,
    make_simple_project,
    month_subject,
    pin_today,
    prepare,
    project_subject,
)
from tests.factories import make_membership, make_user


@pytest.fixture(autouse=True)
def pinned_today(client):
    pin_today(client)


def rows(client, **params) -> list[dict[str, str]]:
    response = client.get(f"{URL}/export/commitments.csv", params=params)
    assert response.status_code == 200
    return list(csv.DictReader(io.StringIO(response.text.removeprefix("\ufeff"))))


def test_the_csv_has_every_commitment_with_what_it_is_about(client):
    municipality, ana = cabinet_member(
        client, others={"projects": "viewer", "environment": "viewer"}
    )
    make_light(municipality, "environment", 2026, 2, "red")
    project = make_simple_project(municipality)
    [old] = held(client, ana, date(2026, 3, 1))
    item = prepare(client)["items"][0]
    commit(client, item, ana, description="=Fórmula", subject=project_subject(project))
    commit(
        client,
        item,
        ana,
        date(2026, 3, 21),
        description="Balanza",
        subject=month_subject("environment", "2026-02"),
    )
    commit(
        client,
        item,
        ana,
        date(2026, 3, 22),
        description="Sin estado",
        subject=month_subject("environment", "2026-01"),
    )
    client.post(f"/api/commitments/{old['id']}/state", json={"state": "done"})

    found = rows(client)

    assert list(found[0]) == [
        "meeting_date",
        "description",
        "owner",
        "due_date",
        "agreed_due_date",
        "state",
        "completed_on",
        "times_postponed",
        "subject_dashboard",
        "subject",
    ]
    assert [tuple(row.values()) for row in found] == [
        (
            "2026-03-10",
            "'=Fórmula",
            "Ana",
            "2026-03-20",
            "2026-03-20",
            "open",
            "",
            "0",
            "projects",
            "Pavimentación",
        ),
        (
            "2026-03-10",
            "Balanza",
            "Ana",
            "2026-03-21",
            "2026-03-21",
            "open",
            "",
            "0",
            "environment",
            "Ambiental, febrero de 2026 (crítico)",
        ),
        (
            "2026-03-10",
            "Sin estado",
            "Ana",
            "2026-03-22",
            "2026-03-22",
            "open",
            "",
            "0",
            "environment",
            "Ambiental, enero de 2026",
        ),
        (
            "2026-02-10",
            "Compromiso 1",
            "Ana",
            "2026-03-01",
            "2026-03-01",
            "done",
            "2026-03-10",
            "1",
            "",
            "",
        ),
    ]


def test_the_csv_takes_the_filters_of_the_list(client):
    _, ana = cabinet_member(client)
    held(client, ana, date(2026, 3, 1), date(2026, 4, 1))

    assert [r["description"] for r in rows(client, state="overdue")] == ["Compromiso 1"]
    assert [r["description"] for r in rows(client, q="2")] == ["Compromiso 2"]
    assert len(rows(client, owner_id=str(ana.id))) == 2


def test_the_csv_is_a_download(client):
    cabinet_member(client, "viewer")

    response = client.get(f"{URL}/export/commitments.csv")

    assert response.headers["content-disposition"] == 'attachment; filename="commitments.csv"'


def test_the_csv_is_of_one_owner_when_asked(client):
    municipality, ana = cabinet_member(client)
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)
    item = prepare(client)["items"][0]
    for owner, name in ((ana, "De Ana"), (leo, "De Leo")):
        commit(client, item, owner, description=name)

    assert [r["description"] for r in rows(client, owner_id=str(leo.id))] == ["De Leo"]
