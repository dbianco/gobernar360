import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import DashboardModule
from gobernar360.main import create_app
from gobernar360.platform.access import AccessLevel, RequestContext, require_dashboard
from gobernar360.platform.models import Membership
from tests.factories import admin_session, login, make_membership, make_municipality, make_user


def _demo_module() -> DashboardModule:
    router = APIRouter()

    @router.get("/read")
    def read(ctx: RequestContext = Depends(require_dashboard("demo", AccessLevel.VIEWER))):
        tenant = ctx.db.scalar(text("SELECT current_setting('app.municipality_id', true)"))
        return {"municipality_id": str(ctx.municipality_id), "db_tenant": tenant}

    @router.post("/write")
    def write(ctx: RequestContext = Depends(require_dashboard("demo", AccessLevel.EDITOR))):
        return {"ok": True}

    @router.put("/settings")
    def settings(ctx: RequestContext = Depends(require_dashboard("demo", AccessLevel.ADMIN))):
        return {"ok": True}

    return DashboardModule(key="demo", router=router, get_summary=lambda ctx, today: [])


@pytest.fixture
def demo_client():
    registry.register(_demo_module())
    try:
        with TestClient(create_app(), headers={"X-Requested-With": "gobernar360"}) as client:
            yield client
    finally:
        registry.unregister("demo")


def _member(grants=None, admin=False, enable=None):
    user = make_user("ana@noetinger.test")
    municipality = make_municipality("Noetinger")
    membership = make_membership(user, municipality, admin=admin, grants=grants, enable=enable)
    return municipality, membership


def _statuses(client) -> tuple[int, int, int]:
    return (
        client.get("/api/dashboards/demo/read").status_code,
        client.post("/api/dashboards/demo/write").status_code,
        client.put("/api/dashboards/demo/settings").status_code,
    )


def test_user_without_grant_is_forbidden(demo_client):
    _member(enable=["demo"])
    login(demo_client, "ana@noetinger.test")

    response = demo_client.get("/api/dashboards/demo/read")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_viewer_can_read_but_not_write(demo_client):
    _member(grants={"demo": "viewer"})
    login(demo_client, "ana@noetinger.test")

    assert _statuses(demo_client) == (200, 403, 403)


def test_editor_can_write_but_not_change_settings(demo_client):
    _member(grants={"demo": "editor"})
    login(demo_client, "ana@noetinger.test")

    assert _statuses(demo_client) == (200, 200, 403)


def test_dashboard_admin_can_change_settings(demo_client):
    _member(grants={"demo": "admin"})
    login(demo_client, "ana@noetinger.test")

    assert _statuses(demo_client) == (200, 200, 200)


def test_municipality_admin_has_admin_level_on_every_enabled_dashboard(demo_client):
    _member(admin=True, enable=["demo"])
    login(demo_client, "ana@noetinger.test")

    assert _statuses(demo_client) == (200, 200, 200)


def test_grant_is_ignored_when_dashboard_is_not_enabled_for_the_municipality(demo_client):
    _member(grants={"demo": "admin"}, enable=[])
    login(demo_client, "ana@noetinger.test")

    assert _statuses(demo_client) == (403, 403, 403)


def test_municipality_admin_cannot_use_a_dashboard_that_is_not_enabled(demo_client):
    _member(admin=True, enable=[])
    login(demo_client, "ana@noetinger.test")

    assert _statuses(demo_client) == (403, 403, 403)


def test_operator_without_membership_cannot_reach_municipality_data(demo_client):
    make_user("operator@gobernar360.test", operator=True)
    make_municipality("Noetinger")
    login(demo_client, "operator@gobernar360.test")

    assert demo_client.get("/api/dashboards/demo/read").status_code == 403


def test_unauthenticated_request_to_a_dashboard_is_rejected(demo_client):
    assert demo_client.get("/api/dashboards/demo/read").status_code == 401


def test_request_is_forbidden_after_membership_is_removed(demo_client):
    _, membership = _member(grants={"demo": "viewer"})
    login(demo_client, "ana@noetinger.test")
    assert demo_client.get("/api/dashboards/demo/read").status_code == 200

    with admin_session() as session, session.begin():
        session.execute(delete(Membership).where(Membership.id == membership.id))

    assert demo_client.get("/api/dashboards/demo/read").status_code == 403
    me = demo_client.get("/api/auth/me").json()
    assert me["memberships"] == []
    assert me["active_municipality_id"] is None
    assert me["dashboards"] == []


def test_request_context_is_scoped_to_the_active_municipality(demo_client):
    municipality, _ = _member(grants={"demo": "viewer"})
    login(demo_client, "ana@noetinger.test")

    body = demo_client.get("/api/dashboards/demo/read").json()

    assert body == {"municipality_id": str(municipality.id), "db_tenant": str(municipality.id)}


def test_me_lists_effective_dashboard_levels(demo_client):
    _member(grants={"demo": "editor"})

    body = login(demo_client, "ana@noetinger.test").json()

    assert body["dashboards"] == [{"key": "demo", "level": "editor"}]


def test_me_omits_dashboards_without_access(demo_client):
    _member(enable=["demo"])

    body = login(demo_client, "ana@noetinger.test").json()

    assert body["dashboards"] == []


def test_without_an_active_municipality_the_reason_is_given(demo_client):
    make_user("operator@gobernar360.test", operator=True)
    make_municipality("Noetinger")
    login(demo_client, "operator@gobernar360.test")

    response = demo_client.get("/api/dashboards/demo/read")

    assert response.json()["error"] == {
        "code": "forbidden",
        "message": "No active municipality is selected.",
    }


def test_a_removed_membership_is_refused_at_once_with_its_reason(demo_client):
    _, membership = _member(grants={"demo": "viewer"})
    login(demo_client, "ana@noetinger.test")

    with admin_session() as session, session.begin():
        session.execute(delete(Membership).where(Membership.id == membership.id))
    response = demo_client.get("/api/dashboards/demo/read")

    assert response.json()["error"] == {
        "code": "forbidden",
        "message": "You do not belong to this municipality.",
    }


def test_a_membership_elsewhere_does_not_open_the_active_municipality(demo_client):
    municipality, membership = _member(grants={"demo": "viewer"})
    user = make_user("beto@noetinger.test")
    make_membership(user, make_municipality("Saira"), grants={"demo": "admin"}, enable=["demo"])
    make_membership(user, municipality)
    login(demo_client, "beto@noetinger.test")
    demo_client.post(
        "/api/auth/active-municipality", json={"municipality_id": str(municipality.id)}
    )

    with admin_session() as session, session.begin():
        session.execute(
            delete(Membership).where(
                Membership.user_id == user.id, Membership.municipality_id == municipality.id
            )
        )

    assert demo_client.get("/api/dashboards/demo/read").json()["error"]["message"] == (
        "You do not belong to this municipality."
    )
