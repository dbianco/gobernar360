"""How residents are told things, and each municipality's own connection to CiDi."""

import json
import logging
import re
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text

from gobernar360.core.config import get_settings
from gobernar360.core.db import get_admin_engine, tenant_session
from gobernar360.platform.cidi import adhesion, connection
from gobernar360.platform.models import AuditLog, MunicipalitySettings
from gobernar360.platform.resident_notice_models import CidiConnectionValue
from tests.factories import (
    REPOSITORY,
    admin_session,
    login,
    make_membership,
    make_municipality,
    make_user,
)
from tests.platform.geo.factories import ADMIN, admin_of, signed_in_admin
from tests.platform.notices import fake_cidi, secrets_key  # noqa: F401

URL = "/api/admin/settings/notices"
SECRET = "s3cr3t-y-muy-largo"
CONNECTED = {
    "resident_notice_channel": "cidi_then_email",
    "cidi_ordinance": "Ordenanza 12.985",
    "adhesion_state": "approved",
    "adhesion_date": "2026-08-01",
    "adhesion_file": "0423-000001/2026",
    "system_name": "gobernar360 – Noetinger",
    "publication_url": "https://noetinger.example",
    "contact": "sistemas@noetinger.test",
}
EMPTY = {
    "resident_notice_channel": "email",
    "cidi_ordinance": "",
    "adhesion_state": "not_requested",
    "adhesion_date": None,
    "adhesion_file": "",
    "system_name": "",
    "publication_url": "",
    "contact": "",
    "secrets": [],
    "missing": ["adhesion", "system_name", "publication_url", "contact"],
    "cidi_available": False,
    "secrets_available": False,
}


def _save(client, url=URL, **changes):
    return client.put(url, json=CONNECTED | changes)


def _error(response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def _entries() -> list[AuditLog]:
    with admin_session() as session:
        return list(session.scalars(select(AuditLog).order_by(AuditLog.created_at)))


# Reading and saving


def test_until_something_is_set_notices_go_by_email(client):
    signed_in_admin(client)

    assert client.get(URL).json() == EMPTY


def test_what_is_saved_is_kept(client):
    signed_in_admin(client)

    saved = _save(client)

    assert saved.status_code == 200
    assert saved.json() == CONNECTED | {
        "secrets": [],
        "missing": [],
        "cidi_available": False,
        "secrets_available": False,
    }
    assert client.get(URL).json() == saved.json()
    # And changed.
    changed = _save(client, resident_notice_channel="cidi", contact=" otra@noetinger.test ")
    assert (changed.json()["resident_notice_channel"], changed.json()["contact"]) == (
        "cidi",
        "otra@noetinger.test",
    )
    back = client.put(URL, json={"resident_notice_channel": "email"}).json()
    assert back == EMPTY | {"secrets_available": False}


def test_whether_cidi_and_secrets_are_available_is_the_installations(
    client,
    fake_cidi,  # noqa: F811
    secrets_key,  # noqa: F811
):
    signed_in_admin(client)

    seen = client.get(URL).json()

    assert (seen["cidi_available"], seen["secrets_available"]) == (True, True)


@pytest.mark.parametrize("channel", ["cidi_then_email", "cidi"])
@pytest.mark.parametrize(
    ("lacking", "missing"),
    [
        ({"adhesion_state": "requested"}, ["adhesion"]),
        ({"adhesion_state": "not_requested", "contact": " "}, ["adhesion", "contact"]),
        ({"system_name": ""}, ["system_name"]),
        ({"publication_url": "", "contact": ""}, ["publication_url", "contact"]),
    ],
)
def test_cidi_is_not_chosen_before_the_adhesion_is_approved_and_complete(
    client, channel, lacking, missing
):
    signed_in_admin(client)

    refused = _save(client, resident_notice_channel=channel, **lacking)

    assert refused.status_code == 422
    assert refused.json()["error"] == {
        "code": "cidi_not_ready",
        "message": "CiDi can be chosen once the adhesion is approved and the connection is "
        "complete.",
        "details": [{"field": name, "message": "missing"} for name in missing],
    }
    assert client.get(URL).json() == EMPTY
    # It may be left for later.
    later = _save(client, resident_notice_channel="email", **lacking)
    assert (later.status_code, later.json()["missing"]) == (200, missing)


def test_going_back_on_the_adhesion_takes_giving_cidi_up(client):
    signed_in_admin(client)
    _save(client)

    assert _error(_save(client, adhesion_state="requested")) == (422, "cidi_not_ready")
    assert client.get(URL).json()["adhesion_state"] == "approved"


@pytest.mark.parametrize(
    "bad",
    [
        {"resident_notice_channel": "sms"},
        {"resident_notice_channel": None},
        {"cidi_ordinance": "x" * 201},
        {"adhesion_state": "denied"},
        {"adhesion_date": "ayer"},
        {"adhesion_file": "x" * 101},
        {"system_name": "x" * 201},
        {"publication_url": "javascript:alert(1)"},
        {"publication_url": "https://" + "x" * 500},
        {"contact": "x" * 201},
        {"removed_secrets": ["No"]},
        {"secrets": [{"name": "No", "value": "x"}]},
        {"secrets": [{"name": "1x", "value": "x"}]},
        {"secrets": [{"name": "x" * 51, "value": "x"}]},
        {"secrets": [{"name": "api_key", "value": ""}]},
        {"secrets": [{"name": "api_key", "value": "x" * 20_001}]},
        {"secrets": [{"name": "api_key"}]},
        {"secrets": [{"name": "api_key", "value": "x", "plain": True}]},
        {"secrets": [{"name": f"k{n}", "value": "x"} for n in range(21)]},
        # These are plain: calling them secret would hide them.
        *({"secrets": [{"name": name, "value": "x"}]} for name in connection.PLAIN_VALUES),
        {"other": 1},
    ],
)
def test_what_is_not_valid_is_refused(client, secrets_key, bad):  # noqa: F811
    signed_in_admin(client)

    assert _error(_save(client, **bad)) == (422, "validation_error")
    assert client.get(URL).json()["adhesion_state"] == "not_requested"


def test_the_longest_texts_are_accepted(client, secrets_key):  # noqa: F811
    signed_in_admin(client)

    saved = _save(
        client,
        cidi_ordinance="x" * 200,
        adhesion_file="x" * 100,
        system_name="x" * 200,
        contact="x" * 200,
        publication_url="https://" + "x" * 492,
        secrets=[{"name": "x" * 50, "value": "x" * 20_000}],
    )

    assert saved.status_code == 200, saved.text


# Secrets


def _stored(name="api_key") -> CidiConnectionValue:
    with admin_session() as session:
        return session.scalars(
            select(CidiConnectionValue).where(CidiConnectionValue.name == name)
        ).one()


def test_a_secret_goes_in_and_never_comes_out(client, secrets_key, caplog):  # noqa: F811
    municipality = signed_in_admin(client)
    before = datetime.now(UTC)

    with caplog.at_level(logging.DEBUG):
        saved = _save(client, secrets=[{"name": "api_key", "value": SECRET}])
        seen = client.get(URL)

    [secret] = saved.json()["secrets"]
    assert secret["name"] == "api_key" and set(secret) == {"name", "set_at"}
    assert datetime.fromisoformat(secret["set_at"]) >= before
    assert seen.json() == saved.json()
    for answer in (saved, seen, client.get("/api/admin/settings")):
        assert SECRET not in answer.text
    assert SECRET not in caplog.text
    # Encrypted in the database, and readable by whoever delivers.
    assert _stored().value is None
    with get_admin_engine().connect() as raw:
        row = raw.execute(
            text("SELECT encrypted, t::text FROM cidi_connection_values t WHERE name = 'api_key'")
        ).one()
    assert SECRET.encode() not in bytes(row[0]) and SECRET not in row[1]
    with tenant_session(municipality.id) as db:
        assert connection.load(db, municipality.id).secrets == {"api_key": SECRET}


def test_the_audit_trail_says_that_a_secret_changed_and_not_to_what(client, secrets_key):  # noqa: F811
    signed_in_admin(client)
    _save(
        client, secrets=[{"name": "token", "value": SECRET}, {"name": "api_key", "value": SECRET}]
    )
    _save(client, removed_secrets=["token", "never_there", "contact"])

    entries = _entries()

    assert SECRET not in json.dumps([entry.changes for entry in entries])
    assert {entry.entity_type for entry in entries} == {"cidi_connections", "municipality_settings"}
    changes = [e.changes for e in entries if "secrets_changed" in e.changes]
    assert changes[0] == {
        "system_name": "gobernar360 – Noetinger",
        "publication_url": "https://noetinger.example",
        "contact": "sistemas@noetinger.test",
        "secrets_changed": ["api_key", "token"],
        "secrets_removed": [],
    }
    assert (changes[1]["secrets_changed"], changes[1]["secrets_removed"]) == ([], ["token"])
    adhesions = [e for e in entries if "adhesion_state" in e.changes]
    assert [e.action for e in adhesions] == ["create", "update"]
    assert adhesions[0].changes == {
        "adhesion_state": "approved",
        "adhesion_date": "2026-08-01",
        "adhesion_file": "0423-000001/2026",
    }
    settings = [e.changes for e in entries if e.entity_type == "municipality_settings"]
    assert settings[0] == {
        "resident_notice_channel": "cidi_then_email",
        "cidi_ordinance": "Ordenanza 12.985",
    }
    assert None not in {entry.user_id for entry in entries}


def test_secrets_left_out_stay_and_those_sent_again_change(client, secrets_key):  # noqa: F811
    municipality = signed_in_admin(client)
    _save(client, secrets=[{"name": "a", "value": "1"}, {"name": "b", "value": "2"}])
    first = _stored("b")

    _save(client, secrets=[{"name": "a", "value": "3"}])
    changed = client.get(URL).json()["secrets"]
    removed = _save(client, removed_secrets=["b", "b"]).json()["secrets"]

    assert [secret["name"] for secret in changed] == ["a", "b"]
    assert datetime.fromisoformat(changed[1]["set_at"]) == first.set_at
    assert datetime.fromisoformat(changed[0]["set_at"]) > first.set_at
    assert [secret["name"] for secret in removed] == ["a"]
    with tenant_session(municipality.id) as db:
        assert connection.load(db, municipality.id).secrets == {"a": "3"}


def test_removing_and_setting_one_at_once_sets_it(client, secrets_key):  # noqa: F811
    municipality = signed_in_admin(client)
    _save(client, secrets=[{"name": "a", "value": "1"}])

    _save(client, secrets=[{"name": "a", "value": "2"}], removed_secrets=["a"])

    with tenant_session(municipality.id) as db:
        assert connection.load(db, municipality.id).secrets == {"a": "2"}


def test_a_plain_value_cannot_be_removed_as_a_secret(client):
    signed_in_admin(client)

    saved = _save(client, removed_secrets=["contact"])

    assert saved.json()["contact"] == "sistemas@noetinger.test"


@pytest.mark.parametrize("key", ["", "not-a-key"])
def test_without_a_key_no_secret_is_accepted(client, monkeypatch, key, caplog):
    monkeypatch.setattr(get_settings(), "secrets_key", key)
    signed_in_admin(client)

    with caplog.at_level(logging.DEBUG):
        refused = _save(client, secrets=[{"name": "api_key", "value": SECRET}])

    assert refused.status_code == 409
    assert refused.json()["error"] == {
        "code": "secrets_key_missing",
        "message": "This installation has no key to keep secrets with.",
    }
    assert SECRET not in caplog.text
    assert client.get(URL).json()["adhesion_state"] == "not_requested"
    # The rest can be saved.
    assert _save(client).status_code == 200


def test_an_error_about_a_secret_does_not_quote_it(client, secrets_key):  # noqa: F811
    signed_in_admin(client)

    for secrets in (
        [{"name": SECRET, "value": SECRET}],
        [{"name": "api_key", "value": SECRET, SECRET: SECRET}],
        [{"name": "api_key", "value": [SECRET]}],
        SECRET,
    ):
        refused = _save(client, secrets=secrets)
        assert _error(refused) == (422, "validation_error")
        assert f'"{SECRET}"' not in refused.text.replace(f".{SECRET}", "")


def test_the_database_takes_a_value_either_plain_or_encrypted():
    municipality = make_municipality()
    now = datetime.now(UTC)
    for fields in ({}, {"value": "x", "encrypted": b"x"}):
        with pytest.raises(Exception, match="plain_or_secret"):
            with admin_session() as session, session.begin():
                session.add(
                    CidiConnectionValue(
                        municipality_id=municipality.id, name="a", set_at=now, **fields
                    )
                )


def test_only_the_delivery_reads_secrets():
    """No route does: `load` is the only place that decrypts, and one module calls it."""
    source = REPOSITORY / "backend/src/gobernar360"
    callers = {
        path.relative_to(source).as_posix()
        for path in source.rglob("*.py")
        if re.search(r"\bsecrets\.decrypt\(|\bconnection\.load\(", path.read_text())
    }
    assert callers == {"platform/cidi/connection.py", "platform/notice_delivery.py"}


# Whose


def test_the_operator_sees_how_far_it_is_and_no_secret(client, secrets_key):  # noqa: F811
    municipality = make_municipality()
    admin_of(municipality)
    make_user("operador@example.test", operator=True)
    login(client, ADMIN)
    _save(client, secrets=[{"name": "api_key", "value": SECRET}])
    client.post("/api/auth/logout")
    login(client, "operador@example.test")
    url = f"/api/platform/municipalities/{municipality.id}/settings/notices"

    seen = client.get(url)

    assert (seen.json()["adhesion_state"], seen.json()["secrets"][0]["name"]) == (
        "approved",
        "api_key",
    )
    assert SECRET not in seen.text
    assert _save(client, url, cidi_ordinance="Otra").json()["cidi_ordinance"] == "Otra"


def test_a_municipality_never_reaches_the_connection_of_another(client, secrets_key):  # noqa: F811
    noetinger, saira = make_municipality(), make_municipality("Saira")
    admin_of(noetinger)
    admin_of(saira, "admin@saira.test")
    login(client, ADMIN)
    _save(client, secrets=[{"name": "api_key", "value": SECRET}])
    client.post("/api/auth/logout")
    login(client, "admin@saira.test")

    assert client.get(URL).json() == EMPTY | {"secrets_available": True}
    _save(client, contact="otra@saira.test", secrets=[{"name": "api_key", "value": "propio"}])
    url = f"/api/platform/municipalities/{noetinger.id}/settings/notices"
    assert _error(client.get(url)) == (403, "forbidden")
    with tenant_session(noetinger.id) as db:
        found = connection.load(db, noetinger.id)
    assert (found.values["contact"], found.secrets) == (
        "sistemas@noetinger.test",
        {"api_key": SECRET},
    )


def test_only_administrators_reach_it(client):
    municipality = make_municipality()
    make_membership(make_user("carla@noetinger.test"), municipality, grants={"complaints": "admin"})
    assert client.get(URL).status_code == 401
    login(client, "carla@noetinger.test")

    for refused in (client.get(URL), _save(client), client.get(f"{URL}/adhesion-request")):
        assert _error(refused) == (403, "forbidden")


def test_each_part_of_the_configuration_leaves_the_rest_alone(client):
    signed_in_admin(client)
    _save(client)

    client.put("/api/admin/settings", json={"notification_emails": ["a@b.test"]})
    client.put(
        "/api/admin/settings/map", json={"small_zone_threshold": 9, "map_background": "cyclosm"}
    )
    assert client.get(URL).json()["resident_notice_channel"] == "cidi_then_email"
    _save(client, cidi_ordinance="Otra")

    rest = client.get("/api/admin/settings").json()
    assert (rest["notification_emails"], rest["small_zone_threshold"], rest["map_background"]) == (
        ["a@b.test"],
        9,
        "cyclosm",
    )
    with admin_session() as session:
        row = session.scalars(select(MunicipalitySettings)).one()
    assert row.updated_by is not None


# The request to the Province


def test_the_request_is_printed_with_what_is_known(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_url", "https://gestion.example")
    municipality = admin_of(make_municipality("Saira & <Cía>"))
    login(client, ADMIN)
    assert municipality is not None

    page = client.get(f"{URL}/adhesion-request")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    for line in (
        "<strong>Nombre del Sistema:</strong> gobernar360 – Saira &amp; &lt;Cía&gt;",
        "<strong>URL de Publicación:</strong> https://gestion.example",
        "<strong>Repartición Pública/Organización:</strong> Saira &amp; &lt;Cía&gt;",
        "<strong>Responsable:</strong> (completar)",
        # Only this scope is asked for.
        "☒ Enviar mensajería a través de CiDi",
        "☐ Acceder con Clave Única de CiDi.",
        "<h2>Leer atentamente</h2>",
    ):
        assert line in page.text
    assert page.text.count("☒") == 1 and page.text.count("☐") == 3
    assert "{{" not in page.text


def test_the_template_in_the_documents_is_the_one_the_app_prints():
    document = (REPOSITORY / "docs/cidi/adhesion-request.md").read_text(encoding="utf-8")

    assert document.endswith(adhesion.request_text("<municipio>", "(completar)"))


def test_the_request_says_what_the_provinces_form_says():
    form = (REPOSITORY / "docs/cidi/source/documentos_cidi_2023_12_19.txt").read_text(
        encoding="utf-8"
    )
    words = " ".join(form.replace("“", '"').replace("”", '"').split())
    text_of = adhesion.request_text("Noetinger", "https://x")

    for sentence in (
        "Por medio de la presente se manifiesta la intención de incorporar el siguiente Sistema "
        "de Información a CiDi.",
        "Este formulario deberá ser presentado o enviado digitalmente ante la autoridad de "
        "aplicación.",
        "Almacenar Documentación en Centro de Documentación Digital.",
        'Mostrar Información registrada en las bases de datos en sección "Mis Datos".',
    ):
        assert sentence in words and sentence in text_of


# Words


@pytest.mark.parametrize(
    "path",
    ["frontend/src/locales/es-AR.json", "backend/src/gobernar360/locales/es-AR.json"],
)
def test_no_text_claims_that_anybody_was_legally_notified(path):
    """Decided by the product owner: the only wording is "Entregado a CiDi"."""
    words = (REPOSITORY / path).read_text(encoding="utf-8")

    assert re.findall(r"(?i)notificad[oa]|fehaciente|notificaci[oó]n electr", words) == []


def test_neither_does_the_api(client):
    schema = json.dumps(client.get("/api/openapi.json").json())

    assert "handed_over_at" in schema
    assert re.findall(r"(?i)\bnotified|notificad", schema) == []
