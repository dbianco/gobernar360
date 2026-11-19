from contextlib import contextmanager
from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text

from gobernar360.core.db import get_admin_engine, tenant_session
from gobernar360.core.errors import ApiError
from gobernar360.platform import people
from gobernar360.platform.access import RequestContext
from gobernar360.platform.models import AuditLog, Person
from gobernar360.platform.people import PersonIn
from tests.factories import make_municipality, make_user


@contextmanager
def context(municipality, user=None):
    user = user or make_user(f"user-{municipality.slug}@example.test")
    with tenant_session(municipality.id) as db:
        yield RequestContext(user=user, municipality_id=municipality.id, membership=None, db=db)


def _person(**fields) -> PersonIn:
    return PersonIn(**({"first_name": "Juana", "last_name": "Pérez"} | fields))


def test_person_is_created_with_a_normalised_dni():
    municipality = make_municipality()

    with context(municipality) as ctx:
        person = people.create_person(
            ctx, _person(dni=" 12.345.678 ", birth_date=date(1990, 5, 1), phone=" 3472 555 ")
        )
        stored = ctx.db.get(Person, person.id)

        assert (stored.dni, stored.birth_date, stored.phone) == (
            "12345678",
            date(1990, 5, 1),
            "3472 555",
        )
        assert (stored.email, stored.address, stored.neighborhood) == ("", "", "")
        assert stored.municipality_id == municipality.id


@pytest.mark.parametrize("dni", ["12", "abc", "1234567890", "12-345-678"])
def test_invalid_dni_is_rejected(dni):
    with pytest.raises(ValidationError):
        _person(dni=dni)


def test_blank_dni_means_no_dni():
    assert _person(dni="  ").dni is None


def test_two_people_without_dni_can_coexist():
    with context(make_municipality()) as ctx:
        people.create_person(ctx, _person())
        people.create_person(ctx, _person(first_name="Otra"))

        assert ctx.db.scalar(select(func.count()).select_from(Person)) == 2


def test_duplicate_dni_in_the_same_municipality_is_rejected():
    with context(make_municipality()) as ctx:
        people.create_person(ctx, _person(dni="12345678"))

        with pytest.raises(ApiError) as error:
            people.create_person(ctx, _person(first_name="Otra", dni="12.345.678"))

        assert (error.value.status_code, error.value.code) == (409, "dni_exists")


def test_same_dni_in_two_municipalities_is_allowed():
    with context(make_municipality("Noetinger")) as ctx:
        people.create_person(ctx, _person(dni="12345678"))
    with context(make_municipality("Saira")) as ctx:
        people.create_person(ctx, _person(dni="12345678"))

        assert ctx.db.scalar(select(func.count()).select_from(Person)) == 1


def test_find_by_dni_does_not_cross_municipalities():
    noetinger, saira = make_municipality("Noetinger"), make_municipality("Saira")
    with context(noetinger) as ctx:
        created = people.create_person(ctx, _person(dni="12345678"))
        assert people.find_by_dni(ctx, "12345678").id == created.id
        assert people.find_by_dni(ctx, "87654321") is None

    with context(saira) as ctx:
        assert people.find_by_dni(ctx, "12345678") is None


def test_update_changes_fields_and_rejects_a_dni_used_by_someone_else():
    with context(make_municipality()) as ctx:
        people.create_person(ctx, _person(dni="12345678"))
        other = people.create_person(ctx, _person(first_name="Otra", dni="22333444"))

        people.update_person(ctx, other, {"neighborhood": "Centro", "dni": "22333444"})
        assert ctx.db.get(Person, other.id).neighborhood == "Centro"

        with pytest.raises(ApiError) as error:
            people.update_person(ctx, other, {"dni": "12345678"})
        assert error.value.code == "dni_exists"

        people.update_person(ctx, other, {"dni": None})
        assert ctx.db.get(Person, other.id).dni is None


def test_changes_are_audited():
    municipality = make_municipality()
    with context(municipality) as ctx:
        person = people.create_person(ctx, _person(dni="12345678"))
        people.update_person(ctx, person, {"phone": "555"})
        people.update_person(ctx, person, {})
        assert people.release_person(ctx, person) is True

        entries = ctx.db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
        assert [(e.action, e.entity_type) for e in entries] == [
            ("create", "people"),
            ("update", "people"),
            ("delete", "people"),
        ]
        assert entries[1].changes == {"phone": "555"}
        assert entries[0].user_id == ctx.user.id
        assert ctx.db.get(Person, person.id) is None


def test_people_table_enforces_tenant_isolation():
    with get_admin_engine().connect() as connection:
        row = connection.execute(
            text(
                "SELECT c.relrowsecurity, c.relforcerowsecurity, "
                "EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid "
                "AND p.polname = 'tenant_isolation') "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = 'people'"
            )
        ).one()

    assert tuple(row) == (True, True, True)
