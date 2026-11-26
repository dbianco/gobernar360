from contextlib import contextmanager
from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from gobernar360.core.db import get_admin_engine, tenant_session
from gobernar360.core.errors import ApiError
from gobernar360.dashboards.social.models import SocialPerson
from gobernar360.platform import people
from gobernar360.platform.access import RequestContext
from gobernar360.platform.models import AuditLog, Person
from gobernar360.platform.people import PersonIn
from gobernar360.platform.publication import names_a_person
from tests.factories import admin_session, make_municipality, make_user


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
        assert entries[0].changes == {
            "first_name": "Juana",
            "last_name": "Pérez",
            "dni": "12345678",
            "cuil": None,
            "birth_date": None,
            "phone": "",
            "email": "",
            "address": "",
            "neighborhood": "",
        }
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


def test_a_text_of_a_person_is_trimmed_and_has_a_limit():
    data = PersonIn(first_name=" Ana ", last_name="Paz", phone=" 11 ", address=" x ")
    assert (data.first_name, data.phone, data.address) == ("Ana", "11", "x")
    assert PersonIn(first_name="Ana", last_name="Paz", phone="1" * 50).phone == "1" * 50
    for field, limit in (("phone", 50), ("email", 200), ("address", 200), ("neighborhood", 100)):
        with pytest.raises(ValidationError):
            PersonIn(first_name="Ana", last_name="Paz", **{field: "x" * (limit + 1)})


def test_a_document_that_is_not_one_says_what_it_must_be():
    for dni in ("12345", "1234567890", "abc"):
        with pytest.raises(ValidationError, match="must have 6 to 9 digits"):
            PersonIn(first_name="Ana", last_name="Paz", dni=dni)


def test_a_person_some_dashboard_still_uses_is_not_released():
    municipality = make_municipality()
    with context(municipality) as ctx:
        person = people.create_person(ctx, _person())
        ctx.db.add(SocialPerson(municipality_id=municipality.id, person_id=person.id))
        ctx.db.flush()

        assert people.release_person(ctx, person) is False

        assert ctx.db.get(Person, person.id) is not None
        assert ctx.db.scalars(select(AuditLog.action)).all() == ["create"]


# CUIL

GOOD = "20123456786"


@pytest.mark.parametrize(
    "typed",
    ["20-12345678-6", "20123456786", " 20.12345678.6 ", "20 12345678 6", "20\u00a012345678-6"],
)
def test_a_cuil_is_stored_in_digits_however_it_is_typed(typed):
    assert _person(cuil=typed).cuil == GOOD


@pytest.mark.parametrize("typed", ["", "  ", "--", None])
def test_a_blank_cuil_is_none(typed):
    assert _person(cuil=typed).cuil is None


@pytest.mark.parametrize(
    "typed",
    [
        "20-12345678-7",
        "20-12345678-0",
        "2012345678",
        "201234567866",
        "20-1234567a-6",
        "٢٠١٢٣٤٥٦٧٨٦",
        # Ten digits no CUIL starts with, whatever the last one.
        *(f"2000000001{last}" for last in range(10)),
    ],
)
def test_a_cuil_that_is_not_one_is_refused(typed):
    with pytest.raises(ValidationError):
        _person(cuil=typed)


@pytest.mark.parametrize(
    ("first_ten", "digit"),
    [
        ("2012345678", 6),
        ("2712345678", 0),
        ("2312345678", 5),
        # 11 minus the remainder is 11, and 10.
        ("2000000000", 1),
        ("2000000001", None),
        ("0000000000", 0),
    ],
)
def test_the_check_digit(first_ten, digit):
    assert people.cuil_check_digit(first_ten) == digit


def test_a_cuil_goes_with_the_document_inside_it():
    municipality = make_municipality()
    with context(municipality) as ctx:
        same = people.create_person(ctx, _person(dni="12345678", cuil=GOOD))
        # Documents have fewer digits than the place they have in a CUIL.
        short = people.create_person(ctx, _person(dni="1234567", cuil="20012345675"))
        alone = people.create_person(ctx, _person(cuil="27111111117"))

        assert (same.cuil, short.cuil) == (GOOD, "20012345675")
        assert (alone.dni, alone.cuil) == (None, "27111111117")


@pytest.mark.parametrize("dni", ["12345679", "2345678", "123456789"])
def test_a_cuil_of_another_document_is_refused(dni):
    municipality = make_municipality()
    with context(municipality) as ctx:
        with pytest.raises(ApiError) as raised:
            people.create_person(ctx, _person(dni=dni, cuil=GOOD))

        assert (raised.value.status_code, raised.value.code, raised.value.message) == (
            422,
            "cuil_dni_mismatch",
            "The CUIL does not match the document number.",
        )
        assert ctx.db.scalar(select(func.count()).select_from(Person)) == 0


def test_the_document_and_the_cuil_go_together_whichever_changes():
    municipality = make_municipality()
    with context(municipality) as ctx:
        person = people.create_person(ctx, _person(dni="12345678"))
        for changes in ({"cuil": "27111111117"}, {"dni": "11111111", "cuil": GOOD}):
            with pytest.raises(ApiError, match="does not match"):
                people.update_person(ctx, person, changes)
        people.update_person(ctx, person, {"cuil": GOOD})
        with pytest.raises(ApiError, match="does not match"):
            people.update_person(ctx, person, {"dni": "11111111"})
        # Both at once, one after taking the other away, and neither.
        people.update_person(ctx, person, {"dni": "11111111", "cuil": "27111111117"})
        people.update_person(ctx, person, {"cuil": None})
        people.update_person(ctx, person, {"dni": "22222222"})
        people.update_person(ctx, person, {"phone": "555"})

        assert (person.dni, person.cuil) == ("22222222", None)


def test_two_people_cannot_share_a_cuil_but_two_municipalities_can():
    noetinger, saira = make_municipality(), make_municipality("Saira")
    with context(noetinger) as ctx:
        first = people.create_person(ctx, _person(cuil=GOOD))
        second = people.create_person(ctx, _person(first_name="Otra"))
        for attempt in (
            lambda: people.create_person(ctx, _person(cuil=GOOD)),
            lambda: people.update_person(ctx, second, {"cuil": GOOD}),
        ):
            with pytest.raises(ApiError) as raised:
                attempt()
            assert (raised.value.status_code, raised.value.code, raised.value.message) == (
                409,
                "cuil_exists",
                "Another person already has this CUIL.",
            )
        # Its own is not somebody else's.
        people.update_person(ctx, first, {"cuil": GOOD})
    with context(saira) as ctx:
        assert people.find_by_cuil(ctx, GOOD) is None
        assert people.create_person(ctx, _person(cuil=GOOD)).cuil == GOOD


def test_the_database_has_the_last_word_on_repeated_cuils():
    municipality = make_municipality()
    for cuil in (GOOD, "2012345678", "2012345678a"):
        with pytest.raises(IntegrityError):
            with admin_session() as session, session.begin():
                for name in ("Uno", "Otro"):
                    session.add(
                        Person(
                            municipality_id=municipality.id,
                            first_name=name,
                            last_name="Sosa",
                            cuil=cuil,
                        )
                    )


def test_somebody_is_looked_up_by_exact_document_or_exact_cuil():
    municipality = make_municipality()
    with context(municipality) as ctx:
        person = people.create_person(ctx, _person(dni="12345678", cuil=GOOD))

        assert people.look_up(ctx, "12.345.678", None) is person
        assert people.look_up(ctx, None, "20-12345678-6") is person
        assert people.look_up(ctx, "87654321", None) is None
        assert people.look_up(ctx, None, "27111111117") is None
        for dni, cuil, message in (
            (None, None, "Send dni or cuil."),
            ("12345678", GOOD, "Send dni or cuil."),
            ("12", None, "dni must have 6 to 9 digits."),
            (None, "20-12345678-7", "cuil is not valid."),
            (None, "", "cuil is not valid."),
        ):
            with pytest.raises(ApiError) as raised:
                people.look_up(ctx, dni, cuil)
            assert (raised.value.status_code, raised.value.code, raised.value.message) == (
                422,
                "validation_error",
                message,
            )


def test_a_report_that_names_a_cuil_names_a_person():
    municipality = make_municipality()
    with context(municipality) as ctx:
        people.create_person(ctx, _person(cuil=GOOD))

        assert names_a_person(ctx, "Se atendió a 20123456786 el lunes.")
        assert names_a_person(ctx, "Se atendió a 20-12345678-6 el lunes.")
        assert not names_a_person(ctx, "Se atendieron 20123456 personas.")
