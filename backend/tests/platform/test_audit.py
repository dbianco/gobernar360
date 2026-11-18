from sqlalchemy import select
from typer.testing import CliRunner

from gobernar360.cli import app
from gobernar360.core.db import platform_session, tenant_session
from gobernar360.platform.access import RequestContext
from gobernar360.platform.audit import apply_audit_fields, record_change
from gobernar360.platform.models import AuditLog, User
from tests.factories import login, make_membership, make_municipality, make_user


def test_record_change_stores_actor_entity_and_changes():
    user = make_user("ana@noetinger.test")
    municipality = make_municipality("Noetinger")
    membership = make_membership(user, municipality)

    with tenant_session(municipality.id) as db:
        ctx = RequestContext(
            user=user, municipality_id=municipality.id, membership=membership, db=db
        )
        record_change(ctx, "update", membership, {"is_admin": True})

    with tenant_session(municipality.id) as db:
        entry = db.scalars(select(AuditLog)).one()
    assert entry.user_id == user.id
    assert entry.municipality_id == municipality.id
    assert (entry.action, entry.entity_type, entry.entity_id) == (
        "update",
        "memberships",
        str(membership.id),
    )
    assert entry.changes == {"is_admin": True}


def test_apply_audit_fields_sets_creator_only_when_creating():
    creator = make_user("ana@noetinger.test")
    editor = make_user("beto@noetinger.test")
    municipality = make_municipality("Noetinger")

    class Entity:
        created_by = None
        updated_by = None
        updated_at = None

    entity = Entity()
    with tenant_session(municipality.id) as db:
        apply_audit_fields(
            RequestContext(creator, municipality.id, None, db), entity, creating=True
        )
        apply_audit_fields(
            RequestContext(editor, municipality.id, None, db), entity, creating=False
        )

    assert entity.created_by == creator.id
    assert entity.updated_by == editor.id
    assert entity.updated_at is not None


def test_user_administration_is_audited(client, demo_dashboard):
    municipality = make_municipality("Noetinger")
    make_membership(make_user("admin@noetinger.test"), municipality, admin=True, enable=["demo"])
    login(client, "admin@noetinger.test")

    client.post(
        "/api/admin/users",
        json={"email": "carla@noetinger.test", "full_name": "Carla", "password": "long-password-1"},
    )

    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog)).all()
    assert [(e.action, e.entity_type) for e in entries] == [("create", "memberships")]


def test_create_operator_command_creates_an_operator_user():
    result = CliRunner().invoke(
        app,
        ["create-operator", "--email", " Operador@Gobernar360.test", "--full-name", "Operador"],
        input="long-password-1\nlong-password-1\n",
    )

    assert result.exit_code == 0, result.output
    with platform_session() as db:
        user = db.scalars(select(User)).one()
    assert user.email == "operador@gobernar360.test"
    assert user.is_platform_operator is True


def test_create_operator_command_rejects_short_passwords():
    result = CliRunner().invoke(
        app,
        ["create-operator", "--email", "op@gobernar360.test", "--full-name", "Operador"],
        input="short\nshort\n",
    )

    assert result.exit_code != 0
    with platform_session() as db:
        assert db.scalars(select(User)).all() == []
