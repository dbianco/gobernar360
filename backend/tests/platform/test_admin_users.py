import pytest

from tests.factories import login, make_membership, make_municipality, make_user


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
        "password": "long-password-1",
        "is_admin": False,
        "grants": {"demo": "editor"},
    } | overrides


def test_admin_lists_only_users_of_the_active_municipality(admin_client):
    other = make_municipality("Saira")
    make_membership(make_user("otro@saira.test"), other)

    users = admin_client.get("/api/admin/users").json()

    assert [u["user"]["email"] for u in users] == ["admin@noetinger.test"]


def test_admin_lists_enabled_dashboards(admin_client):
    assert admin_client.get("/api/admin/dashboards").json() == ["demo"]


def test_admin_creates_user_with_grants(admin_client, client):
    response = admin_client.post("/api/admin/users", json=_new_user())

    assert response.status_code == 201
    assert response.json()["grants"] == {"demo": "editor"}
    client.post("/api/auth/logout")
    me = login(client, "carla@noetinger.test", "long-password-1").json()
    assert me["dashboards"] == [{"key": "demo", "level": "editor"}]


def test_creating_user_with_existing_email_in_same_municipality_returns_conflict(admin_client):
    admin_client.post("/api/admin/users", json=_new_user())

    response = admin_client.post("/api/admin/users", json=_new_user(email=" Carla@Noetinger.TEST "))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_admin_cannot_add_an_account_that_already_exists_elsewhere(admin_client, client):
    # Whoever registered the email first chose its password, so letting an administrator
    # attach it to their municipality would hand that person access to it.
    other = make_municipality("Saira")
    make_membership(make_user("carla@noetinger.test"), other)

    response = admin_client.post("/api/admin/users", json=_new_user())
    forced = admin_client.post("/api/admin/users", json=_new_user(existing_account="keep_password"))

    assert (response.status_code, forced.status_code) == (409, 409)
    assert response.json()["error"]["code"] == "account_exists"
    client.post("/api/auth/logout")
    me = login(client, "carla@noetinger.test").json()
    assert [m["municipality"]["name"] for m in me["memberships"]] == ["Saira"]


def test_grant_for_a_dashboard_that_is_not_enabled_is_rejected(admin_client):
    response = admin_client.post("/api/admin/users", json=_new_user(grants={"other": "viewer"}))

    assert response.status_code == 422


def test_unknown_grant_level_is_rejected(admin_client):
    response = admin_client.post("/api/admin/users", json=_new_user(grants={"demo": "owner"}))

    assert response.status_code == 422


def test_short_password_is_rejected(admin_client):
    response = admin_client.post("/api/admin/users", json=_new_user(password="short"))

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


def test_admin_removes_a_member_but_not_the_user_account(admin_client, client):
    membership_id = admin_client.post("/api/admin/users", json=_new_user()).json()["membership_id"]

    assert admin_client.delete(f"/api/admin/users/{membership_id}").status_code == 204

    assert len(admin_client.get("/api/admin/users").json()) == 1
    client.post("/api/auth/logout")
    me = login(client, "carla@noetinger.test", "long-password-1").json()
    assert me["memberships"] == []


def test_last_admin_cannot_demote_or_remove_themselves(admin_client):
    own_id = admin_client.get("/api/admin/users").json()[0]["membership_id"]

    demote = admin_client.patch(f"/api/admin/users/{own_id}", json={"is_admin": False})
    remove = admin_client.delete(f"/api/admin/users/{own_id}")

    assert demote.status_code == 409
    assert remove.status_code == 409
    assert demote.json()["error"]["code"] == "conflict"


def test_admin_can_step_down_when_another_admin_exists(admin_client):
    admin_client.post("/api/admin/users", json=_new_user(is_admin=True))
    own = next(
        u
        for u in admin_client.get("/api/admin/users").json()
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
        for m in admin_client.get("/api/admin/users").json()
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
