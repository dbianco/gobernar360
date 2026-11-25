"""What every route that writes owes: a trace of exactly what was written, and a clear no to
ids that are not the municipality's."""

import uuid

from sqlalchemy import select

from gobernar360.platform.models import AuditLog, Municipality
from tests.factories import (
    admin_session,
    enable_dashboards,
    login,
    make_membership,
    make_municipality,
    make_user,
)


def administrator(client, dashboard: str) -> Municipality:
    """Sign in the administrator of a municipality with the dashboard."""
    municipality = make_municipality()
    enable_dashboards(municipality, [dashboard])
    make_membership(make_user("admin@noetinger.test"), municipality, admin=True, enable=[])
    login(client, "admin@noetinger.test")
    return municipality


def trail() -> list[AuditLog]:
    with admin_session() as session:
        return list(session.scalars(select(AuditLog).order_by(AuditLog.created_at)))


def write(client, method: str, url: str, body: dict):
    response = client.request(method, url, json=body)
    assert response.status_code in (200, 201, 204), (url, response.text)
    return response


def check_trace(client, method: str, url: str, body: dict, action: str, **more) -> None:
    """The request leaves one entry with what was written, and nothing it did not say."""
    before = {entry.id for entry in trail()}
    write(client, method, url, body)
    [entry] = [entry for entry in trail() if entry.id not in before]
    assert entry.action == action, url
    expected = body | more
    if action == "update":
        assert entry.changes == expected, url
    else:
        # Defaults are written too.
        assert entry.changes is not None, url
        assert {key: entry.changes.get(key) for key in expected} == expected, url


def check_reference(client, method: str, url: str, body: dict, field: str) -> None:
    """An id that is not the municipality's is refused, by its name and without a trace."""
    before = len(trail())
    response = client.request(method, url, json=body | {field: str(uuid.uuid4())})
    assert response.status_code == 422, (url, response.text)
    assert response.json()["error"] == {
        "code": "invalid_reference",
        "message": f"{field} does not reference an existing record.",
    }, url
    assert len(trail()) == before, url
