"""Configuración: a municipality's recipients, single sign-on switch and email texts."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from gobernar360.platform.clock import get_today
from gobernar360.platform.email_templates import to_text
from gobernar360.platform.geo import backgrounds
from gobernar360.platform.models import AuditLog
from gobernar360.platform.texts import format_datetime
from tests.factories import (
    admin_session,
    configure,
    emails_to,
    login,
    make_membership,
    make_municipality,
    make_user,
)

INVITATION = {
    "subject": "Bienvenida a {{municipality}}",
    "html": "<p>Hola {{name}}, entrá acá: <a href='{{link}}'>elegir contraseña</a></p>",
}


MAP_BACKGROUNDS = [vars(background) for background in backgrounds.BACKGROUNDS]


@pytest.fixture
def noetinger():
    return make_municipality("Noetinger")


@pytest.fixture
def admin_client(client, noetinger):
    make_membership(make_user("admin@noetinger.test"), noetinger, admin=True)
    login(client, "admin@noetinger.test")
    return client


def _template(client, key: str) -> dict:
    return next(t for t in client.get("/api/admin/email-templates").json() if t["key"] == key)


def test_settings_start_empty_with_single_sign_on_off(admin_client):
    assert admin_client.get("/api/admin/settings").json() == {
        "notification_emails": [],
        "sso_enabled": False,
        "sso_available": False,
        "small_zone_threshold": 5,
        "map_background": "standard",
        "map_api_key": None,
        "map_backgrounds": MAP_BACKGROUNDS,
    }


def test_admin_saves_the_recipients_normalised_and_without_repeats(admin_client):
    response = admin_client.put(
        "/api/admin/settings",
        json={
            "notification_emails": [
                " Jefa@Noetinger.test ",
                "prensa@example.test",
                "jefa@noetinger.test",
            ],
            "sso_enabled": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["notification_emails"] == ["jefa@noetinger.test", "prensa@example.test"]
    assert admin_client.get("/api/admin/settings").json()["sso_enabled"] is True
    with admin_session() as session:
        entry = session.scalars(select(AuditLog)).one()
    assert entry.entity_type == "municipality_settings"
    assert entry.changes["sso_enabled"] is True


def test_a_malformed_recipient_is_rejected(admin_client):
    response = admin_client.put(
        "/api/admin/settings", json={"notification_emails": ["ok@example.test", "no-es-un-email"]}
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "notification_emails.1"


def test_only_the_municipality_s_administrators_reach_its_configuration(client, noetinger):
    make_membership(make_user("carla@noetinger.test"), noetinger, grants={"demo": "admin"})
    make_user("operator@gobernar360.test", operator=True)

    anonymous = client.get("/api/admin/settings").status_code
    login(client, "carla@noetinger.test")
    member = [
        client.get("/api/admin/settings").status_code,
        client.put("/api/admin/settings", json={"sso_enabled": True}).status_code,
        client.get("/api/admin/email-templates").status_code,
    ]
    client.post("/api/auth/logout")
    login(client, "operator@gobernar360.test")
    operator = client.get("/api/admin/settings").status_code

    assert (anonymous, member, operator) == (401, [403, 403, 403], 403)


def test_each_municipality_sees_only_its_own_configuration(admin_client):
    saira = make_municipality("Saira")
    configure(saira, ["saira@example.test"], sso=True)
    make_membership(make_user("admin@saira.test"), saira, admin=True)

    assert admin_client.get("/api/admin/settings").json()["notification_emails"] == []
    admin_client.put("/api/admin/email-templates/invitation", json=INVITATION)
    admin_client.post("/api/auth/logout")
    login(admin_client, "admin@saira.test")
    assert _template(admin_client, "invitation")["customized"] is False


# Email texts


def test_every_kind_of_email_is_listed_with_its_variables(admin_client):
    templates = {t["key"]: t for t in admin_client.get("/api/admin/email-templates").json()}

    assert list(templates) == [
        "invitation",
        "membership_added",
        "password_reset",
        "status_light_missing",
        "milestone_overdue",
    ]
    assert templates["invitation"]["variables"] == [
        "name",
        "inviter",
        "municipality",
        "link",
        "expires",
    ]
    assert templates["invitation"]["required"] == ["link"]
    assert templates["milestone_overdue"]["required"] == ["items"]
    assert all(not t["customized"] for t in templates.values())
    assert "{{link}}" in templates["invitation"]["html"]


def test_a_saved_text_is_sanitised(admin_client):
    response = admin_client.put(
        "/api/admin/email-templates/invitation",
        json={
            "subject": "  Hola\n{{name}}  ",
            "html": '<p onclick="x()">Hola</p><script>alert(1)</script>'
            '<a href="{{link}}">entrar</a><a href="javascript:alert(1)">mal</a><img src="x">',
        },
    )

    assert response.status_code == 200
    saved = response.json()
    assert saved["subject"] == "Hola {{name}}"
    assert saved["html"] == '<p>Hola</p><a href="{{link}}">entrar</a><a>mal</a>'
    assert saved["customized"] is True


def test_a_text_cannot_use_variables_its_email_does_not_have(admin_client):
    response = admin_client.put(
        "/api/admin/email-templates/password_reset",
        json={"subject": "Hola", "html": "<p>{{link}} de {{municipality}}</p>"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "template_unknown_variable"
    assert error["details"] == [{"field": "html", "message": "municipality"}]


def test_a_text_must_keep_the_variables_its_email_needs(admin_client):
    response = admin_client.put(
        "/api/admin/email-templates/invitation",
        json={"subject": "Hola", "html": "<p>Bienvenida, {{name}}</p>"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "template_missing_variable"
    assert response.json()["error"]["details"] == [{"field": "html", "message": "link"}]


def test_the_list_of_events_cannot_go_in_the_subject(admin_client):
    response = admin_client.put(
        "/api/admin/email-templates/milestone_overdue",
        json={"subject": "Hitos: {{items}}", "html": "<p>{{items}}</p>"},
    )

    assert response.status_code == 422


def test_an_unknown_kind_of_email_is_not_found(admin_client):
    response = admin_client.put("/api/admin/email-templates/lottery", json=INVITATION)

    assert response.status_code == 404


def test_invitations_use_the_municipality_s_text_with_values_escaped(admin_client):
    admin_client.put("/api/admin/email-templates/invitation", json=INVITATION)

    admin_client.post(
        "/api/admin/users",
        json={"email": "carla@noetinger.test", "full_name": "Carla <b>Carga</b>"},
    )

    [email] = emails_to("carla@noetinger.test")
    assert email.subject == "Bienvenida a Noetinger"
    assert "Hola Carla &lt;b&gt;Carga&lt;/b&gt;, entrá acá:" in email.body_html
    assert '<a href="http://localhost:5173/set-password#' in email.body_html
    assert email.body.startswith("Hola Carla <b>Carga</b>, entrá acá: elegir contraseña (http")


def test_restoring_the_default_text(admin_client):
    admin_client.put("/api/admin/email-templates/invitation", json=INVITATION)

    restored = admin_client.delete("/api/admin/email-templates/invitation").json()
    admin_client.post(
        "/api/admin/users", json={"email": "carla@noetinger.test", "full_name": "Carla"}
    )

    assert restored["customized"] is False
    assert _template(admin_client, "invitation")["customized"] is False
    [email] = emails_to("carla@noetinger.test")
    assert email.subject == "Te dieron acceso a Noetinger en gobernar360"


def test_admin_gets_a_test_email_of_the_text_being_edited(admin_client):
    response = admin_client.post("/api/admin/email-templates/invitation/test", json=INVITATION)

    assert response.status_code == 204
    [email] = emails_to("admin@noetinger.test")
    assert email.subject == "[Prueba] Bienvenida a Noetinger"
    assert "Hola Admin, entrá acá" in email.body
    # Nothing was saved.
    assert _template(admin_client, "invitation")["customized"] is False


def test_a_test_email_of_an_invalid_text_is_refused(admin_client):
    response = admin_client.post(
        "/api/admin/email-templates/invitation/test", json={"subject": "x", "html": "<p>x</p>"}
    )

    assert response.status_code == 422
    assert emails_to("admin@noetinger.test") == []


def test_recovery_uses_the_text_of_the_only_municipality_of_the_account(
    admin_client, client, noetinger
):
    admin_client.put(
        "/api/admin/email-templates/password_reset",
        json={"subject": "Recuperá tu clave de Noetinger", "html": "<p>{{link}}</p>"},
    )
    make_membership(make_user("leo@noetinger.test"), noetinger)
    make_membership(make_user("sara@saira.test"), make_municipality("Saira"))
    client.post("/api/auth/logout")

    client.post("/api/auth/password-reset", json={"email": "leo@noetinger.test"})
    client.post("/api/auth/password-reset", json={"email": "sara@saira.test"})

    assert emails_to("leo@noetinger.test")[0].subject == "Recuperá tu clave de Noetinger"
    assert emails_to("sara@saira.test")[0].subject == "Elegí una contraseña nueva para gobernar360"


def test_recovery_of_an_account_in_several_municipalities_uses_the_default_text(
    admin_client, client, noetinger
):
    admin_client.put(
        "/api/admin/email-templates/password_reset",
        json={"subject": "Recuperá tu clave de Noetinger", "html": "<p>{{link}}</p>"},
    )
    carla = make_user("carla@noetinger.test")
    make_membership(carla, noetinger)
    make_membership(carla, make_municipality("Saira"))
    client.post("/api/auth/logout")

    client.post("/api/auth/password-reset", json={"email": "carla@noetinger.test"})

    [email] = emails_to("carla@noetinger.test")
    assert email.subject == "Elegí una contraseña nueva para gobernar360"


def test_plain_text_version_keeps_paragraphs_lists_and_links():
    html = (
        "<h2>Título</h2><p>Hola,<br>Ana</p><ul><li>uno</li><li><a href='https://x.test'>dos</a>"
        "</li></ul><p><a href='https://y.test'>https://y.test</a></p>"
    )

    assert to_text(html) == (
        "Título\n\nHola,\nAna\n\n• uno\n• dos (https://x.test)\n\nhttps://y.test\n"
    )


def test_a_test_email_fills_every_variable_with_believable_values(admin_client):
    admin_client.app.dependency_overrides[get_today] = lambda: date(2026, 3, 10)
    before = format_datetime(datetime.now(UTC) + timedelta(days=7))
    admin_client.post(
        "/api/admin/email-templates/invitation/test",
        json={
            "subject": "{{name}} / {{inviter}} / {{municipality}}",
            "html": "<p>{{link}} | {{expires}}</p>",
        },
    )
    after = format_datetime(datetime.now(UTC) + timedelta(days=7))
    admin_client.post(
        "/api/admin/email-templates/milestone_overdue/test",
        json={
            "subject": "{{municipality}} {{month}}",
            "html": "<p>{{account_link}}</p>{{items}}",
        },
    )

    invitation, notification = emails_to("admin@noetinger.test")
    assert invitation.subject == "[Prueba] Admin / Admin / Noetinger"
    assert invitation.body in (
        f"http://localhost:5173/login | {before}\n",
        f"http://localhost:5173/login | {after}\n",
    )
    assert notification.subject == "[Prueba] Noetinger febrero"
    assert notification.body == "http://localhost:5173/account\n\n• Un aviso de ejemplo\n"
    assert "<ul><li>Un aviso de ejemplo</li></ul>" in notification.body_html


def test_an_account_added_to_another_municipality_is_told_in_that_municipality_s_words(
    admin_client, noetinger
):
    admin_client.put(
        "/api/admin/email-templates/membership_added",
        json={
            "subject": "{{inviter}} te sumó a {{municipality}}",
            "html": "<p>Hola {{name}}: entrá en {{link}}</p>",
        },
    )
    make_membership(make_user("carla@saira.test"), make_municipality("Saira"))

    admin_client.post(
        "/api/admin/users",
        json={"email": "carla@saira.test", "full_name": "Otro nombre", "grants": {}},
    )

    [email] = emails_to("carla@saira.test")
    assert email.subject == "Admin te sumó a Noetinger"
    # The account keeps the name its owner gave it.
    assert email.body == "Hola Carla: entrá en http://localhost:5173/login\n"


# The platform operator configures any municipality


@pytest.fixture
def operator_client(client):
    make_user("operator@gobernar360.test", operator=True)
    login(client, "operator@gobernar360.test")
    return client


def test_the_operator_reads_and_changes_the_configuration_of_a_municipality(
    operator_client, noetinger
):
    saira = make_municipality("Saira")
    url = f"/api/platform/municipalities/{noetinger.id}"

    saved = operator_client.put(
        f"{url}/settings",
        json={"notification_emails": ["jefa@noetinger.test"], "sso_enabled": True},
    )
    template = operator_client.put(f"{url}/email-templates/invitation", json=INVITATION)

    assert (saved.status_code, template.status_code) == (200, 200)
    assert operator_client.get(f"{url}/settings").json() == {
        "notification_emails": ["jefa@noetinger.test"],
        "sso_enabled": True,
        "sso_available": False,
        "small_zone_threshold": 5,
        "map_background": "standard",
        "map_api_key": None,
        "map_backgrounds": MAP_BACKGROUNDS,
    }
    theirs = {t["key"]: t for t in operator_client.get(f"{url}/email-templates").json()}
    assert theirs["invitation"]["subject"] == INVITATION["subject"]
    # Another municipality is untouched.
    other = f"/api/platform/municipalities/{saira.id}"
    assert operator_client.get(f"{other}/settings").json()["notification_emails"] == []
    others = {t["key"]: t for t in operator_client.get(f"{other}/email-templates").json()}
    assert others["invitation"]["customized"] is False


def test_the_operator_restores_a_default_text_and_gets_the_test_email(operator_client, noetinger):
    url = f"/api/platform/municipalities/{noetinger.id}/email-templates/invitation"
    operator_client.put(url, json=INVITATION)

    sent = operator_client.post(f"{url}/test", json=INVITATION)
    restored = operator_client.delete(url)

    assert (sent.status_code, restored.status_code) == (204, 200)
    assert restored.json()["customized"] is False
    assert len(emails_to("operator@gobernar360.test")) == 1


def test_the_operator_s_changes_are_in_the_municipality_s_audit_log(operator_client, noetinger):
    url = f"/api/platform/municipalities/{noetinger.id}/settings"

    operator_client.put(url, json={"notification_emails": [], "sso_enabled": True})

    with admin_session() as session:
        entry = session.scalars(select(AuditLog)).one()
    assert (entry.municipality_id, entry.entity_type) == (noetinger.id, "municipality_settings")


def test_a_municipality_administrator_cannot_use_the_operator_s_routes(admin_client, noetinger):
    url = f"/api/platform/municipalities/{noetinger.id}"

    assert admin_client.get(f"{url}/settings").status_code == 403
    assert admin_client.put(f"{url}/settings", json={"sso_enabled": True}).status_code == 403
    assert admin_client.get(f"{url}/email-templates").status_code == 403


def test_the_operator_gets_not_found_for_a_municipality_that_does_not_exist(operator_client):
    url = "/api/platform/municipalities/00000000-0000-0000-0000-000000000000/settings"

    assert operator_client.get(url).status_code == 404


def test_a_text_saved_again_replaces_the_one_before(admin_client):
    for subject in ("Primero {{municipality}}", "Segundo {{municipality}}"):
        saved = admin_client.put(
            "/api/admin/email-templates/invitation",
            json={"subject": subject, "html": "<p>{{link}}</p>"},
        )
        assert saved.status_code == 200, saved.text

    assert _template(admin_client, "invitation")["subject"] == "Segundo {{municipality}}"
    assert _template(admin_client, "invitation")["customized"] is True


def test_restoring_a_text_that_is_already_the_default_changes_nothing(admin_client):
    before = _template(admin_client, "invitation")

    restored = admin_client.delete("/api/admin/email-templates/invitation")

    assert (restored.status_code, restored.json()) == (200, before)
