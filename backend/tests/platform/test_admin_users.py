import pytest
from sqlalchemy import select

from gobernar360.platform.models import AuditLog
from tests.factories import (
    accept_invitation,
    admin_session,
    emails_to,
    link_token,
    login,
    make_membership,
    make_municipality,
    make_user,
)


@pytest.fixture
def municipality(demo_dashboard):
    return make_municipality("Noetinger")


@pytest.fixture
def admin_client(client, municipality):
    admin = make_user("admin@noetinger.test")
    make_membership(admin, municipality, admin=True, enable=["demo"])
    login(client, "admin@noetinger.test")
    return client


def _new_user(**overrides):
    return {
        "email": "carla@noetinger.test",
        "full_name": "Carla Carga",
        "is_admin": False,
        "grants": {"demo": "editor"},
    } | overrides


def test_admin_lists_only_users_of_the_active_municipality(admin_client):
    other = make_municipality("Saira")
    make_membership(make_user("otro@saira.test"), other)

    users = admin_client.get("/api/admin/users").json()["items"]

    assert [u["user"]["email"] for u in users] == ["admin@noetinger.test"]


def test_admin_lists_enabled_dashboards(admin_client):
    assert admin_client.get("/api/admin/dashboards").json() == ["demo"]


def test_admin_creates_user_with_grants(admin_client, client):
    response = admin_client.post("/api/admin/users", json=_new_user())

    assert response.status_code == 201
    assert response.json()["grants"] == {"demo": "editor"}
    client.post("/api/auth/logout")
    accept_invitation(client, "carla@noetinger.test", "long-password-1")
    me = login(client, "carla@noetinger.test", "long-password-1").json()
    assert me["dashboards"] == [{"key": "demo", "level": "editor"}]


def test_adding_a_new_email_asks_no_password_and_emails_an_invitation(admin_client, client):
    # A password in the request is ignored: only the owner of the email chooses one.
    admin_client.post("/api/admin/users", json=_new_user(password="typed-by-the-admin"))
    client.post("/api/auth/logout")

    signed_in = client.post(
        "/api/auth/login",
        json={"email": "carla@noetinger.test", "password": "typed-by-the-admin"},
    )

    assert signed_in.status_code == 401
    [invitation] = emails_to("carla@noetinger.test")
    assert invitation.subject == "Te dieron acceso a Noetinger en gobernar360"
    assert "Carla Carga" in invitation.body
    assert "Admin" in invitation.body  # who invited them
    assert "http://localhost:5173/set-password#" in invitation.body


def test_creating_user_with_existing_email_in_same_municipality_returns_conflict(admin_client):
    admin_client.post("/api/admin/users", json=_new_user())

    response = admin_client.post("/api/admin/users", json=_new_user(email=" Carla@Noetinger.TEST "))

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "conflict",
        "message": "This user already belongs to the municipality.",
    }


def test_adding_an_existing_account_answers_exactly_like_a_new_one(admin_client, client):
    # Accounts are shared between municipalities. The administrator must not learn that
    # one existed, nor get a way into it: the owner keeps their password and is told.
    make_membership(make_user("carla@noetinger.test"), make_municipality("Saira"))

    existing = admin_client.post("/api/admin/users", json=_new_user(full_name="Carla"))
    new = admin_client.post(
        "/api/admin/users", json=_new_user(email="nueva@noetinger.test", full_name="Carla")
    )

    assert existing.status_code == new.status_code == 201
    assert existing.json().keys() == new.json().keys()
    assert [len(emails_to("carla@noetinger.test")), len(emails_to("nueva@noetinger.test"))] == [
        1,
        1,
    ]
    assert "/set-password" not in emails_to("carla@noetinger.test")[0].body
    client.post("/api/auth/logout")
    me = login(client, "carla@noetinger.test").json()
    assert sorted(m["municipality"]["name"] for m in me["memberships"]) == ["Noetinger", "Saira"]


def test_admin_resends_an_invitation_and_only_the_newest_link_works(admin_client, client):
    member_id = admin_client.post("/api/admin/users", json=_new_user()).json()["membership_id"]

    response = admin_client.post(f"/api/admin/users/{member_id}/invitation")

    assert response.status_code == 204
    first, second = emails_to("carla@noetinger.test")
    client.post("/api/auth/logout")
    stale = client.post(
        "/api/auth/tokens/redeem",
        json={"token": link_token(first), "password": "long-password-1"},
    )
    assert stale.status_code == 410
    accept_invitation(client, "carla@noetinger.test", "long-password-1")


def test_resending_to_an_account_with_a_password_answers_the_same_and_sends_nothing(
    admin_client,
):
    make_membership(make_user("carla@noetinger.test"), make_municipality("Saira"))
    member_id = admin_client.post("/api/admin/users", json=_new_user()).json()["membership_id"]

    response = admin_client.post(f"/api/admin/users/{member_id}/invitation")

    assert response.status_code == 204
    assert len(emails_to("carla@noetinger.test")) == 1  # the notice of the first addition


def test_admin_cannot_resend_an_invitation_for_another_municipality(admin_client):
    foreign = make_membership(
        make_user("otro@saira.test", password=None), make_municipality("Saira")
    )

    response = admin_client.post(f"/api/admin/users/{foreign.id}/invitation")

    assert response.status_code == 404
    assert emails_to("otro@saira.test") == []


def test_grant_for_a_dashboard_that_is_not_enabled_is_rejected(admin_client):
    response = admin_client.post(
        "/api/admin/users",
        json=_new_user(grants={"zeta": "viewer", "demo": "viewer", "other": "editor"}),
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "validation_error",
        "message": "Dashboards not enabled for this municipality: other, zeta.",
    }


def test_unknown_grant_level_is_rejected(admin_client):
    response = admin_client.post("/api/admin/users", json=_new_user(grants={"demo": "owner"}))

    assert response.status_code == 422


def test_email_without_at_sign_is_rejected(admin_client):
    assert admin_client.post("/api/admin/users", json=_new_user(email="carla")).status_code == 422


def test_admin_changes_grant_level(admin_client):
    membership_id = admin_client.post("/api/admin/users", json=_new_user()).json()["membership_id"]

    response = admin_client.patch(
        f"/api/admin/users/{membership_id}", json={"grants": {"demo": "viewer"}}
    )

    assert response.status_code == 200
    assert response.json()["grants"] == {"demo": "viewer"}


def test_admin_revokes_access_by_sending_empty_grants(admin_client):
    membership_id = admin_client.post("/api/admin/users", json=_new_user()).json()["membership_id"]

    response = admin_client.patch(f"/api/admin/users/{membership_id}", json={"grants": {}})

    assert response.json()["grants"] == {}


def test_admin_promotes_a_member_to_admin(admin_client):
    membership_id = admin_client.post("/api/admin/users", json=_new_user()).json()["membership_id"]

    response = admin_client.patch(f"/api/admin/users/{membership_id}", json={"is_admin": True})

    assert response.json()["is_admin"] is True
    assert response.json()["grants"] == {"demo": "editor"}


def test_admin_cannot_edit_membership_of_another_municipality(admin_client):
    other = make_municipality("Saira")
    foreign = make_membership(make_user("otro@saira.test"), other)

    patch = admin_client.patch(f"/api/admin/users/{foreign.id}", json={"is_admin": True})
    delete = admin_client.delete(f"/api/admin/users/{foreign.id}")

    assert patch.status_code == 404
    assert delete.status_code == 404
    assert patch.json()["error"] == {
        "code": "not_found",
        "message": "User not found in this municipality.",
    }


def test_admin_removes_a_member_but_not_the_user_account(admin_client, client):
    membership_id = admin_client.post("/api/admin/users", json=_new_user()).json()["membership_id"]

    assert admin_client.delete(f"/api/admin/users/{membership_id}").status_code == 204

    assert len(admin_client.get("/api/admin/users").json()["items"]) == 1
    client.post("/api/auth/logout")
    accept_invitation(client, "carla@noetinger.test", "long-password-1")
    me = login(client, "carla@noetinger.test", "long-password-1").json()
    assert me["memberships"] == []


def test_last_admin_cannot_demote_or_remove_themselves(admin_client):
    own_id = admin_client.get("/api/admin/users").json()["items"][0]["membership_id"]

    demote = admin_client.patch(f"/api/admin/users/{own_id}", json={"is_admin": False})
    remove = admin_client.delete(f"/api/admin/users/{own_id}")

    assert demote.status_code == 409
    assert remove.status_code == 409
    assert (
        demote.json()["error"]
        == remove.json()["error"]
        == {
            "code": "conflict",
            "message": "The municipality must keep at least one administrator.",
        }
    )


def test_admin_can_step_down_when_another_admin_exists(admin_client):
    admin_client.post("/api/admin/users", json=_new_user(is_admin=True))
    own = next(
        u
        for u in admin_client.get("/api/admin/users").json()["items"]
        if u["user"]["email"] == "admin@noetinger.test"
    )

    response = admin_client.patch(
        f"/api/admin/users/{own['membership_id']}", json={"is_admin": False}
    )

    assert response.status_code == 200


def test_non_admin_cannot_manage_users(client, municipality):
    make_membership(make_user("ana@noetinger.test"), municipality, grants={"demo": "admin"})
    login(client, "ana@noetinger.test")

    assert client.get("/api/admin/users").status_code == 403
    assert client.post("/api/admin/users", json=_new_user()).status_code == 403


def test_member_grants_of_a_disabled_dashboard_are_hidden_and_do_not_block_edits(
    admin_client, municipality
):
    from gobernar360.platform.models import MunicipalityDashboard
    from tests.factories import admin_session

    member = make_membership(
        make_user("carla@noetinger.test"),
        municipality,
        grants={"demo": "viewer", "projects": "editor"},
    )
    with admin_session() as session, session.begin():
        session.delete(session.get(MunicipalityDashboard, (municipality.id, "projects")))

    listed = next(
        m
        for m in admin_client.get("/api/admin/users").json()["items"]
        if m["membership_id"] == str(member.id)
    )
    response = admin_client.patch(
        f"/api/admin/users/{member.id}", json={"grants": listed["grants"] | {"demo": "editor"}}
    )

    assert listed["grants"] == {"demo": "viewer"}
    assert response.status_code == 200
    assert response.json()["grants"] == {"demo": "editor"}
    # The hidden grant survives, so access comes back if the dashboard is enabled again.
    with admin_session() as session:
        stored = session.get(type(member), member.id).grants
        assert {g.dashboard_key: g.level for g in stored} == {
            "demo": "editor",
            "projects": "editor",
        }


def test_a_deactivated_account_is_added_and_not_written_to(client):
    municipality = make_municipality("Noetinger")
    make_membership(make_user("admin@noetinger.test"), municipality, admin=True)
    make_user("ida@noetinger.test", password=None, active=False)
    login(client, "admin@noetinger.test")

    response = client.post(
        "/api/admin/users", json={"email": "ida@noetinger.test", "full_name": "Ida"}
    )

    assert response.status_code == 201
    assert emails_to("ida@noetinger.test") == []


def test_the_last_administrator_is_counted_in_their_own_municipality(client):
    noetinger, saira = make_municipality("Noetinger"), make_municipality("Saira")
    own = make_membership(make_user("admin@noetinger.test"), noetinger, admin=True)
    # Administrators elsewhere do not make up for it.
    for name in ("uno", "dos"):
        make_membership(make_user(f"{name}@saira.test"), saira, admin=True)
    login(client, "admin@noetinger.test")
    url = f"/api/admin/users/{own.id}"
    refusal = {
        "code": "conflict",
        "message": "The municipality must keep at least one administrator.",
    }

    for response in (client.patch(url, json={"is_admin": False}), client.delete(url)):
        assert response.status_code == 409
        assert response.json()["error"] == refusal
    rows = "email,nombre,administrador\nadmin@noetinger.test,Admin,no\n"
    imported = client.post("/api/admin/users/import", json={"csv": rows})
    assert imported.status_code == 409
    assert imported.json()["error"] == refusal


def test_members_are_listed_by_name_whatever_its_capitals_then_by_email(admin_client):
    for full_name, email in (
        ("Zoe", "a@noetinger.test"),
        ("ana", "d@noetinger.test"),
        ("Bruno", "c@noetinger.test"),
        ("Ana", "e@noetinger.test"),
        ("ana", "b@noetinger.test"),
    ):
        admin_client.post("/api/admin/users", json=_new_user(full_name=full_name, email=email))

    users = admin_client.get("/api/admin/users", params={"q": "@noetinger"}).json()["items"]
    emails = [item["user"]["email"][0] for item in users if item["user"]["email"][1] == "@"]

    assert emails == ["b", "d", "e", "c", "a"]


def test_members_are_searched_by_name_and_by_email(admin_client):
    admin_client.post("/api/admin/users", json=_new_user())

    def found(q: str) -> list[str]:
        items = admin_client.get("/api/admin/users", params={"q": q}).json()["items"]
        return [item["user"]["full_name"] for item in items]

    assert found("carga") == ["Carla Carga"]
    assert found("carla@") == ["Carla Carga"]
    assert found("nadie") == []


def test_what_changed_in_a_member_s_access_is_in_the_audit_log(admin_client):
    membership_id = admin_client.post("/api/admin/users", json=_new_user()).json()["membership_id"]
    url = f"/api/admin/users/{membership_id}"

    admin_client.patch(url, json={"is_admin": True})
    admin_client.patch(url, json={"grants": {"demo": "viewer"}})
    admin_client.delete(url)

    with admin_session() as session:
        entries = session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == "memberships")
            .order_by(AuditLog.created_at)
        ).all()
    assert [(entry.action, entry.changes) for entry in entries] == [
        (
            "create",
            {
                "email": "carla@noetinger.test",
                "is_admin": False,
                "grants": {"demo": "editor"},
            },
        ),
        ("update", {"is_admin": True}),
        ("update", {"grants": {"demo": "viewer"}}),
        ("delete", {"email": "carla@noetinger.test"}),
    ]
    assert {str(entry.entity_id) for entry in entries} == {membership_id}
