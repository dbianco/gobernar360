"""Builders for cabinet-dashboard test data.

Meetings and commitments are made through the API, as people make them; only what the API
would not allow (the past, another municipality) is written through the owner connection.
"""

from datetime import date

from fastapi.testclient import TestClient

from gobernar360.platform.clock import get_today
from gobernar360.platform.models import DashboardStatus, Municipality, User
from tests.factories import (
    admin_session,
    login,
    make_membership,
    make_municipality,
    make_user,
)
from tests.projects.factories import make_axis, make_department, make_project, make_term

URL = "/api/dashboards/cabinet"
TODAY = date(2026, 3, 10)
EMAIL = "ana@noetinger.test"
ALL = ("projects", "environment", "economic", "social", "procedures", "cabinet")


def pin_today(client: TestClient, today: date = TODAY) -> None:
    client.app.dependency_overrides[get_today] = lambda: today


def cabinet_member(
    client: TestClient,
    level: str | None = "editor",
    email: str = EMAIL,
    municipality: Municipality | None = None,
    others: dict[str, str] | None = None,
    enable: tuple[str, ...] = ALL,
    municipality_name: str = "Noetinger",
) -> tuple[Municipality, User]:
    """Sign in a member with `level` on cabinet and whatever `others` says elsewhere."""
    municipality = municipality or make_municipality(municipality_name)
    grants = dict(others or {})
    if level:
        grants["cabinet"] = level
    user = make_user(email)
    make_membership(user, municipality, grants=grants, enable=list(enable))
    login(client, email)
    return municipality, user


def as_member(client: TestClient, email: str = EMAIL) -> None:
    client.cookies.clear()
    login(client, email)


def make_light(municipality, key: str, year: int, month: int, color: str) -> None:
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


def make_simple_project(municipality, name: str = "Pavimentación"):
    term = make_term(municipality)
    axis, department = make_axis(municipality, term), make_department(municipality)
    return make_project(municipality, term, axis, department, name=name)


def project_subject(project) -> dict:
    return {"dashboard_key": "projects", "kind": "project", "ref": str(project.id)}


def month_subject(key: str, ref: str) -> dict:
    return {"dashboard_key": key, "kind": "month", "ref": ref}


def prepare(client: TestClient, on: date = TODAY, agenda=("Temas varios",), **fields) -> dict:
    """Prepare a meeting; text in `agenda` is an item of one's own, a dict goes as it is."""
    entries = [{"title": entry} if isinstance(entry, str) else entry for entry in agenda]
    response = client.post(
        f"{URL}/meetings", json={"date": on.isoformat(), "agenda": entries, **fields}
    )
    assert response.status_code == 201, response.text
    return response.json()


def commit(client: TestClient, item: dict, owner, due: date = date(2026, 3, 20), **fields) -> dict:
    response = client.post(
        f"{URL}/items/{item['id']}/commitments",
        json={
            "description": "Certificar la obra",
            "owner_id": str(owner.id),
            "due_date": due.isoformat(),
        }
        | fields,
    )
    assert response.status_code == 201, response.text
    return response.json()


def close(client: TestClient, meeting: dict) -> dict:
    response = client.post(f"{URL}/meetings/{meeting['id']}/close")
    assert response.status_code == 200, response.text
    return response.json()


def held(client: TestClient, owner, *dues: date, on: date = date(2026, 2, 10)) -> list[dict]:
    """A closed meeting that took one commitment per due date."""
    meeting = prepare(client, on)
    taken = [
        commit(client, meeting["items"][0], owner, due, description=f"Compromiso {n}")
        for n, due in enumerate(dues, start=1)
    ]
    close(client, meeting)
    return taken


def proposal(client: TestClient, on: date = TODAY) -> dict:
    response = client.get(f"{URL}/agenda-proposal", params={"date": on.isoformat()})
    assert response.status_code == 200, response.text
    return response.json()


def error(response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]
