"""Suspending a municipality: its data stays, nobody works in it until it is resumed."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.main import create_app
from gobernar360.platform.models import AuditLog
from tests.factories import login, make_membership, make_municipality, make_user

REASON = "Cambio de gestión: la nueva intendencia revisa el contrato."


@pytest.fixture
def operator(client, demo_dashboard):
    make_user("operator@gobernar360.test", operator=True)
    login(client, "operator@gobernar360.test")
    return client


@pytest.fixture
def member(demo_dashboard):
    """A second browser, where a member of two municipalities is already signed in."""
    noetinger, saira = make_municipality("Noetinger"), make_municipality("Saira")
    user = make_user("ana@noetinger.test")
    make_membership(user, noetinger, admin=True, grants={"demo": "viewer"})
    make_membership(user, saira, grants={"demo": "viewer"})
    with TestClient(create_app(), headers={"X-Requested-With": "gobernar360"}) as browser:
        login(browser, "ana@noetinger.test")
        browser.post("/api/auth/active-municipality", json={"municipality_id": str(noetinger.id)})
        browser.noetinger, browser.saira = noetinger, saira
        yield browser


def _suspend(operator, municipality, reason=REASON):
    return operator.post(
        f"/api/platform/municipalities/{municipality.id}/suspension", json={"reason": reason}
    )


def _resume(operator, municipality):
    return operator.delete(f"/api/platform/municipalities/{municipality.id}/suspension")


def _listed(operator, municipality):
    listed = operator.get("/api/platform/municipalities").json()
    return next(item for item in listed if item["id"] == str(municipality.id))


def test_the_operator_sees_the_state_and_the_reason(operator, member):
    assert _listed(operator, member.noetinger)["suspension"] is None

    response = _suspend(operator, member.noetinger, f"  {REASON}  ")

    assert response.status_code == 201, response.text
    suspension = response.json()["suspension"]
    assert suspension["reason"] == REASON
    assert suspension["by"] == "Operator"
    assert datetime.fromisoformat(suspension["at"])
    assert _listed(operator, member.noetinger)["suspension"] == suspension
    assert _listed(operator, member.saira)["suspension"] is None


def test_a_signed_in_member_is_refused_from_the_next_request(operator, member):
    assert member.get("/api/overview").status_code == 200

    _suspend(operator, member.noetinger)

    for method, path in [
        ("get", "/api/overview"),
        ("get", "/api/admin/users"),
        ("get", "/api/dashboards/demo/status?year=2026"),
        ("post", "/api/admin/users"),
    ]:
        response = getattr(member, method)(path)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "municipality_suspended", path


def test_a_suspended_municipality_leaves_the_switcher(operator, member):
    _suspend(operator, member.noetinger)

    me = member.get("/api/auth/me").json()

    assert [m["municipality"]["name"] for m in me["memberships"]] == ["Saira"]
    assert me["active_municipality_id"] is None
    assert me["dashboards"] == []
    assert [m["name"] for m in me["suspended_municipalities"]] == ["Noetinger"]
    # Nor can it be chosen again.
    chosen = member.post(
        "/api/auth/active-municipality", json={"municipality_id": str(member.noetinger.id)}
    )
    assert chosen.status_code == 403
    assert chosen.json()["error"]["code"] == "municipality_suspended"


def test_the_members_other_municipality_keeps_working(operator, member):
    _suspend(operator, member.noetinger)

    switched = member.post(
        "/api/auth/active-municipality", json={"municipality_id": str(member.saira.id)}
    )

    assert switched.status_code == 200
    assert member.get("/api/overview").status_code == 200


def test_resuming_restores_everything_as_it_was(operator, member):
    before = member.get("/api/admin/users").json()
    _suspend(operator, member.noetinger)

    response = _resume(operator, member.noetinger)

    assert response.status_code == 200, response.text
    assert response.json()["suspension"] is None
    me = member.get("/api/auth/me").json()
    # The same session is back in the same municipality, with the same access.
    assert me["active_municipality_id"] == str(member.noetinger.id)
    assert me["suspended_municipalities"] == []
    assert me["dashboards"] == [{"key": "demo", "level": "admin"}]
    assert member.get("/api/admin/users").json() == before


def test_signing_in_to_a_suspended_municipality_shows_it_suspended(operator):
    noetinger = make_municipality("Noetinger")
    make_membership(make_user("solo@noetinger.test"), noetinger, grants={"demo": "viewer"})
    _suspend(operator, noetinger)
    with TestClient(create_app(), headers={"X-Requested-With": "gobernar360"}) as browser:
        me = login(browser, "solo@noetinger.test").json()
        assert me["memberships"] == []
        assert [m["slug"] for m in me["suspended_municipalities"]] == ["noetinger"]
        assert browser.get("/api/overview").json()["error"]["code"] == "municipality_suspended"

        _resume(operator, noetinger)

        # Its only municipality becomes active again without choosing it.
        assert browser.get("/api/auth/me").json()["active_municipality_id"] == str(noetinger.id)
        assert browser.get("/api/overview").status_code == 200


def test_suspending_needs_a_reason_and_a_state_to_change(operator):
    noetinger = make_municipality("Noetinger")

    assert _suspend(operator, noetinger, "   ").status_code == 422
    assert _resume(operator, noetinger).status_code == 409
    assert _suspend(operator, noetinger).status_code == 201
    assert _suspend(operator, noetinger).status_code == 409


def test_suspending_and_resuming_are_audited(operator):
    noetinger = make_municipality("Noetinger")

    _suspend(operator, noetinger)
    _resume(operator, noetinger)

    with tenant_session(noetinger.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert [(e.entity_type, e.changes) for e in entries] == [
        ("municipalities", {"suspended": True, "reason": REASON}),
        ("municipalities", {"suspended": False}),
    ]


def test_only_the_operator_suspends(member):
    # A municipality administrator cannot suspend or resume, not even their own.
    path = f"/api/platform/municipalities/{member.noetinger.id}/suspension"

    assert member.post(path, json={"reason": "x"}).status_code == 403
    assert member.delete(path).status_code == 403
    assert member.get("/api/overview").status_code == 200


def test_the_operator_still_configures_a_suspended_municipality(operator, member):
    _suspend(operator, member.noetinger)

    users = operator.get(f"/api/platform/municipalities/{member.noetinger.id}/users")

    assert users.status_code == 200
    assert [u["user"]["email"] for u in users.json()] == ["ana@noetinger.test"]
