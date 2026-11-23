"""Members listed page by page, and added or updated from a CSV file."""

import csv
import io

import pytest
from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform import members_csv
from gobernar360.platform.models import AuditLog
from tests.factories import (
    emails_to,
    login,
    make_membership,
    make_municipality,
    make_user,
)

HEADER = "email,nombre,administrador,Proyectos,Ambiental"


@pytest.fixture
def noetinger():
    return make_municipality("Noetinger")


@pytest.fixture
def admin_client(client, noetinger):
    make_membership(
        make_user("admin@noetinger.test"), noetinger, admin=True, enable=["projects", "environment"]
    )
    login(client, "admin@noetinger.test")
    return client


def _import(client, content: str):
    return client.post("/api/admin/users/import", json={"csv": content})


def _members(client) -> dict[str, dict]:
    items = client.get("/api/admin/users", params={"limit": 200}).json()["items"]
    return {member["user"]["email"]: member for member in items}


# Pagination


def test_members_are_listed_by_name_one_page_at_a_time(admin_client, noetinger):
    for name in ("zoe", "bea", "carla", "Ana"):
        make_membership(make_user(f"{name}@noetinger.test"), noetinger)

    first = admin_client.get("/api/admin/users", params={"limit": 2}).json()
    second = admin_client.get("/api/admin/users", params={"limit": 2, "offset": 2}).json()
    last = admin_client.get("/api/admin/users", params={"limit": 2, "offset": 4}).json()

    names = [m["user"]["full_name"] for page in (first, second, last) for m in page["items"]]
    assert names == ["Admin", "Ana", "Bea", "Carla", "Zoe"]
    assert (first["total"], len(first["items"]), len(last["items"])) == (5, 2, 1)


def test_page_size_has_limits(admin_client):
    assert admin_client.get("/api/admin/users", params={"limit": 0}).status_code == 422
    assert admin_client.get("/api/admin/users", params={"limit": 201}).status_code == 422


# The example file


def test_the_example_has_the_header_and_two_people(admin_client):
    response = admin_client.get("/api/admin/users/import-template.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="usuarios-ejemplo.csv"' in response.headers["content-disposition"]
    assert response.content.startswith("\ufeff".encode())
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows == [
        ["email", "nombre", "administrador", "Ambiental", "Proyectos"],
        ["ana.perez@ejemplo.gob.ar", "Ana Pérez", "no", "Carga", "Lectura"],
        ["juan.gomez@ejemplo.gob.ar", "Juan Gómez", "sí", "", ""],
    ]


def test_the_example_imports_as_it_is(admin_client):
    example = admin_client.get("/api/admin/users/import-template.csv").content.decode("utf-8")

    response = _import(admin_client, example)

    assert response.json() == {"created": 2, "updated": 0, "unchanged": 0}
    members = _members(admin_client)
    assert members["ana.perez@ejemplo.gob.ar"]["grants"] == {
        "environment": "editor",
        "projects": "viewer",
    }
    assert members["juan.gomez@ejemplo.gob.ar"]["is_admin"] is True


# Importing


def test_import_adds_members_and_invites_them(admin_client):
    response = _import(
        admin_client,
        f"{HEADER}\n"
        "carla@noetinger.test,Carla Carga,no,Carga,\n"
        "leo@noetinger.test,Leo,no,,Lectura\n",
    )

    assert response.status_code == 200
    assert response.json() == {"created": 2, "updated": 0, "unchanged": 0}
    members = _members(admin_client)
    assert members["carla@noetinger.test"]["grants"] == {"projects": "editor"}
    assert members["leo@noetinger.test"]["grants"] == {"environment": "viewer"}
    assert "/set-password#" in emails_to("carla@noetinger.test")[0].body
    assert len(emails_to("leo@noetinger.test")) == 1


def test_the_last_row_for_an_email_wins_and_invites_once(admin_client):
    content = (
        f"{HEADER}\n"
        "carla@noetinger.test,Carla,no,Lectura,Lectura\n"
        "leo@noetinger.test,Leo,no,Lectura,\n"
        " CARLA@noetinger.test ,Carla,no,Administración,\n"
    )

    response = _import(admin_client, content)

    assert response.json() == {"created": 2, "updated": 0, "unchanged": 0}
    assert _members(admin_client)["carla@noetinger.test"]["grants"] == {"projects": "admin"}
    assert len(emails_to("carla@noetinger.test")) == 1


def test_a_later_file_updates_the_access_of_existing_members(admin_client):
    _import(admin_client, f"{HEADER}\ncarla@noetinger.test,Carla,no,Lectura,Lectura\n")

    response = _import(
        admin_client,
        f"{HEADER}\ncarla@noetinger.test,Carla,sí,Carga,\nadmin@noetinger.test,Admin,sí,,\n",
    )

    assert response.json() == {"created": 0, "updated": 1, "unchanged": 1}
    carla = _members(admin_client)["carla@noetinger.test"]
    assert (carla["is_admin"], carla["grants"]) == (True, {"projects": "editor"})
    # Only adding someone sends an email.
    assert len(emails_to("carla@noetinger.test")) == 1


def test_a_dashboard_column_left_out_keeps_that_access(admin_client):
    _import(admin_client, f"{HEADER}\ncarla@noetinger.test,Carla,no,Carga,Lectura\n")

    _import(admin_client, "email,nombre,Proyectos\ncarla@noetinger.test,Carla,Lectura\n")

    carla = _members(admin_client)["carla@noetinger.test"]
    assert carla["grants"] == {"projects": "viewer", "environment": "viewer"}
    assert carla["is_admin"] is False


def test_semicolons_spanish_or_api_names_case_and_accents_are_all_accepted(admin_client):
    content = (
        "Correo;Nombre y apellido;ADMINISTRADOR;projects;AMBIENTAL\n"
        "carla@noetinger.test;Carla;SI;administracion;viewer\n"
        "leo@noetinger.test;Leo;No;sin acceso;EDITOR\n"
    )

    response = _import(admin_client, "\ufeff" + content)

    assert response.json()["created"] == 2
    members = _members(admin_client)
    assert members["carla@noetinger.test"]["is_admin"] is True
    assert members["carla@noetinger.test"]["grants"] == {
        "projects": "admin",
        "environment": "viewer",
    }
    assert members["leo@noetinger.test"]["grants"] == {"environment": "editor"}


def test_an_existing_account_from_elsewhere_is_added_with_a_notice(admin_client):
    make_membership(make_user("sara@saira.test"), make_municipality("Saira"))

    _import(admin_client, f"{HEADER}\nsara@saira.test,Sara,no,Lectura,\n")

    [notice] = emails_to("sara@saira.test")
    assert "/set-password" not in notice.body
    assert _members(admin_client)["sara@saira.test"]["grants"] == {"projects": "viewer"}


def test_every_problem_is_reported_with_its_line_and_nothing_changes(admin_client):
    content = (
        f"{HEADER}\n"
        "carla@noetinger.test,Carla,no,Lectura,\n"
        "no-es-un-email,Leo,no,,\n"
        "\n"
        "ana@noetinger.test,,quizás,Jefa,\n"
        "bea@noetinger.test,Bea,no,,,extra\n"
    )

    response = _import(admin_client, content)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_csv"
    assert [(d["line"], d["code"], d["column"], d["value"]) for d in error["details"]] == [
        (3, "invalid_email", "email", "no-es-un-email"),
        (5, "missing_name", "nombre", ""),
        (5, "invalid_admin", "administrador", "quizás"),
        (5, "invalid_level", "Proyectos", "Jefa"),
        (6, "extra_cells", "", ""),
    ]
    assert list(_members(admin_client)) == ["admin@noetinger.test"]
    assert emails_to("carla@noetinger.test") == []


def test_wrong_columns_are_reported_on_line_one(admin_client):
    response = _import(admin_client, "correo,Trámites,Color\nx@noetinger.test,Lectura,rojo\n")

    details = response.json()["error"]["details"]
    assert [(d["line"], d["code"], d["column"]) for d in details] == [
        (1, "dashboard_not_enabled", "Trámites"),
        (1, "unknown_column", "Color"),
        (1, "missing_column", "nombre"),
    ]


def test_an_empty_file_is_refused(admin_client):
    for content in ("", f"{HEADER}\n\n"):
        response = _import(admin_client, content)
        assert response.status_code == 422
        assert response.json()["error"]["details"][0]["code"] == "no_rows"


def test_too_many_rows_are_refused(admin_client, monkeypatch):
    monkeypatch.setattr(members_csv, "MAX_ROWS", 2)
    rows = "".join(f"u{i}@noetinger.test,U{i},no,,\n" for i in range(3))

    response = _import(admin_client, f"{HEADER}\n{rows}")

    assert response.json()["error"]["details"][0]["code"] == "too_many_rows"
    assert list(_members(admin_client)) == ["admin@noetinger.test"]


def test_an_import_cannot_leave_the_municipality_without_administrator(admin_client):
    response = _import(
        admin_client, f"{HEADER}\nadmin@noetinger.test,Admin,no,,\ncarla@noetinger.test,C,no,,\n"
    )

    assert response.status_code == 409
    assert _members(admin_client)["admin@noetinger.test"]["is_admin"] is True
    assert "carla@noetinger.test" not in _members(admin_client)
    assert emails_to("carla@noetinger.test") == []


def test_an_import_may_hand_the_role_to_someone_else(admin_client):
    response = _import(
        admin_client, f"{HEADER}\nadmin@noetinger.test,Admin,no,,\ncarla@noetinger.test,C,sí,,\n"
    )

    assert response.json() == {"created": 1, "updated": 1, "unchanged": 0}


def test_only_administrators_import(client, noetinger):
    make_membership(make_user("carla@noetinger.test"), noetinger, grants={"projects": "admin"})
    login(client, "carla@noetinger.test")

    assert _import(client, f"{HEADER}\nx@noetinger.test,X,no,,\n").status_code == 403
    assert client.get("/api/admin/users/import-template.csv").status_code == 403


def test_the_operator_imports_into_a_municipality_too(client, noetinger):
    make_user("operator@gobernar360.test", operator=True)
    login(client, "operator@gobernar360.test")
    url = f"/api/platform/municipalities/{noetinger.id}/users"

    response = client.post(
        f"{url}/import", json={"csv": "email,nombre,administrador\nines@noetinger.test,Inés,sí\n"}
    )

    assert response.json()["created"] == 1
    assert client.get(url).json()["items"][0]["is_admin"] is True


def test_members_are_searched_by_name_or_email_ignoring_accents(admin_client, noetinger):
    make_membership(make_user("jose@noetinger.test"), noetinger)
    make_membership(make_user("ines@saira.test"), noetinger)

    def emails(q):
        items = admin_client.get("/api/admin/users", params={"q": q}).json()["items"]
        return [member["user"]["email"] for member in items]

    assert emails("JOSÉ") == ["jose@noetinger.test"]
    assert emails("saira") == ["ines@saira.test"]
    assert emails("noetinger admin") == ["admin@noetinger.test"]
    result = admin_client.get("/api/admin/users", params={"q": "noetinger", "limit": 1}).json()
    assert (result["total"], len(result["items"])) == (2, 1)


def _audit(noetinger) -> list[tuple[str, dict]]:
    with tenant_session(noetinger.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)).all()
        return [(entry.action, entry.changes) for entry in entries]


def test_an_import_is_audited_row_by_row(admin_client, noetinger):
    _import(admin_client, f"{HEADER}\ncarla@noetinger.test,Carla,no,Lectura,\n")

    _import(
        admin_client,
        f"{HEADER}\nadmin@noetinger.test,Admin,sí,,\ncarla@noetinger.test,Carla,sí,Carga,\n",
    )

    assert _audit(noetinger) == [
        (
            "create",
            {"email": "carla@noetinger.test", "is_admin": False, "grants": {"projects": "viewer"}},
        ),
        ("update", {"is_admin": True, "grants": {"projects": "editor"}, "source": "csv"}),
    ]


def test_rows_that_change_nothing_are_counted_and_the_rest_still_applied(admin_client):
    _import(admin_client, f"{HEADER}\ncarla@noetinger.test,Carla,no,Lectura,\n")

    response = _import(
        admin_client,
        f"{HEADER}\n"
        "admin@noetinger.test,Admin,sí,,\n"
        "carla@noetinger.test,Carla,no,Lectura,\n"
        "leo@noetinger.test,Leo,no,,Carga\n",
    )

    assert response.json() == {"created": 1, "updated": 0, "unchanged": 2}
    assert _members(admin_client)["leo@noetinger.test"]["grants"] == {"environment": "editor"}


def test_several_updates_are_all_counted(admin_client):
    _import(
        admin_client,
        f"{HEADER}\ncarla@noetinger.test,Carla,no,Lectura,\nleo@noetinger.test,Leo,no,Lectura,\n",
    )

    response = _import(
        admin_client,
        f"{HEADER}\ncarla@noetinger.test,Carla,no,Carga,\nleo@noetinger.test,Leo,no,,Carga\n",
    )

    assert response.json() == {"created": 0, "updated": 2, "unchanged": 0}
