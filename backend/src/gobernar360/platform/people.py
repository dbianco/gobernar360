"""The municipality's registry of people, shared by the dashboards that work with residents.

It has no routes of its own: each dashboard reaches the registry through these
helpers and decides which people it shows. A dashboard may only look a person up
by exact document number or CUIL, so it never browses people it did not incorporate.
"""

import re
import uuid
from datetime import date
from typing import Annotated, Any, ClassVar

from fastapi import Query
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    StringConstraints,
    TypeAdapter,
    ValidationError,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from gobernar360.core.errors import (
    cuil_dni_mismatch,
    cuil_exists,
    dni_exists,
    validation_error,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.api_types import OrmModel, PatchModel
from gobernar360.platform.audit import record_change
from gobernar360.platform.models import Person
from gobernar360.platform.tenant_crud import create_entity, update_entity

DNI_PATTERN = re.compile(r"\d{6,9}")


def _strip_dni(value: Any) -> Any:
    """People type documents as 12.345.678; a blank one means the person has none."""
    if isinstance(value, str):
        return value.replace(".", "").replace(" ", "") or None
    return value


def _check_dni(value: str) -> str:
    if not DNI_PATTERN.fullmatch(value):
        raise ValueError("must have 6 to 9 digits")
    return value


Dni = Annotated[str, BeforeValidator(_strip_dni), AfterValidator(_check_dni)]

CUIL_PATTERN = re.compile(r"[0-9]{11}")
CUIL_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
# Where the document is inside a CUIL, after the two digits of its kind.
CUIL_DNI = slice(2, 10)


def cuil_check_digit(first_ten: str) -> int | None:
    """The last digit of a CUIL, or None when none starts with those ten."""
    total = sum(int(digit) * weight for digit, weight in zip(first_ten, CUIL_WEIGHTS, strict=True))
    digit = 11 - total % 11
    if digit == 11:
        return 0
    return None if digit == 10 else digit


def _strip_cuil(value: Any) -> Any:
    """People type it as 20-12345678-6; a blank one means the person has none."""
    if isinstance(value, str):
        return re.sub(r"[-.\s]", "", value) or None
    return value


def _check_cuil(value: str) -> str:
    if not CUIL_PATTERN.fullmatch(value):
        raise ValueError("must have 11 digits")
    if cuil_check_digit(value[:10]) != int(value[10]):
        raise ValueError("the last digit is not right")
    return value


Cuil = Annotated[str, BeforeValidator(_strip_cuil), AfterValidator(_check_cuil)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def _text(max_length: int) -> Any:
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=max_length)]


Phone = _text(50)
Email = _text(200)
Address = _text(200)
Neighborhood = _text(100)


class PersonIn(BaseModel):
    first_name: PersonName
    last_name: PersonName
    dni: Annotated[Dni | None, BeforeValidator(_strip_dni)] = None
    cuil: Annotated[Cuil | None, BeforeValidator(_strip_cuil)] = None
    birth_date: date | None = None
    phone: Phone = ""
    email: Email = ""
    address: Address = ""
    neighborhood: Neighborhood = ""


class PersonPatch(PatchModel):
    nullable: ClassVar[frozenset[str]] = frozenset({"dni", "cuil", "birth_date"})

    first_name: PersonName | None = None
    last_name: PersonName | None = None
    dni: Annotated[Dni | None, BeforeValidator(_strip_dni)] = None
    cuil: Annotated[Cuil | None, BeforeValidator(_strip_cuil)] = None
    birth_date: date | None = None
    phone: Phone | None = None
    email: Email | None = None
    address: Address | None = None
    neighborhood: Neighborhood | None = None


class PersonOut(OrmModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str
    dni: str | None
    cuil: str | None
    birth_date: date | None
    phone: str
    email: str
    address: str
    neighborhood: str


def find_by_dni(ctx: RequestContext, dni: str) -> Person | None:
    return ctx.db.scalar(select(Person).where(Person.dni == dni))


def find_by_cuil(ctx: RequestContext, cuil: str) -> Person | None:
    return ctx.db.scalar(select(Person).where(Person.cuil == cuil))


# A document as somebody looks it up.
DocumentQuery = Annotated[str | None, Query(max_length=30)]

_dni = TypeAdapter(Dni)
_cuil = TypeAdapter(Cuil)


def look_up(ctx: RequestContext, dni: str | None, cuil: str | None) -> Person | None:
    """The person with exactly this document number, or exactly this CUIL: one of the two."""
    if (dni is None) == (cuil is None):
        raise validation_error("Send dni or cuil.")
    try:
        if dni is not None:
            return find_by_dni(ctx, _dni.validate_python(dni))
        return find_by_cuil(ctx, _cuil.validate_python(cuil))
    except ValidationError as error:
        if dni is not None:
            raise validation_error("dni must have 6 to 9 digits.") from error
        raise validation_error("cuil is not valid.") from error


def find_same(ctx: RequestContext, data: PersonIn) -> Person | None:
    """Whoever of the registry the data is about: by document and, failing that, by CUIL."""
    found = find_by_dni(ctx, data.dni) if data.dni else None
    if found is None and data.cuil:
        found = find_by_cuil(ctx, data.cuil)
    return found


def _check_cuil_of(
    ctx: RequestContext, dni: str | None, cuil: str | None, person: Person | None
) -> None:
    if cuil is None:
        return
    if dni is not None and cuil[CUIL_DNI] != dni.zfill(8):
        raise cuil_dni_mismatch()
    holder = find_by_cuil(ctx, cuil)
    if holder is not None and (person is None or holder.id != person.id):
        raise cuil_exists()


def _ensure_dni_is_free(ctx: RequestContext, dni: str | None, person: Person | None) -> None:
    if dni is None:
        return
    holder = find_by_dni(ctx, dni)
    if holder is not None and (person is None or holder.id != person.id):
        raise dni_exists()


def create_person(ctx: RequestContext, data: PersonIn) -> Person:
    _ensure_dni_is_free(ctx, data.dni, None)
    _check_cuil_of(ctx, data.dni, data.cuil, None)
    return create_entity(ctx, Person(**data.model_dump()), data.model_dump())


def update_person(ctx: RequestContext, person: Person, changes: dict[str, Any]) -> Person:
    """Apply the given fields; an empty set of changes leaves no trace."""
    if not changes:
        return person
    if "dni" in changes:
        _ensure_dni_is_free(ctx, changes["dni"], person)
    if "dni" in changes or "cuil" in changes:
        # Each must go with the other, whichever of them changes.
        _check_cuil_of(
            ctx, changes.get("dni", person.dni), changes.get("cuil", person.cuil), person
        )
    return update_entity(ctx, person, changes)


def release_person(ctx: RequestContext, person: Person) -> bool:
    """Drop a person no dashboard uses any more, so no personal data lingers unseen.

    Returns False, leaving the person in place, while any record still references them.
    """
    try:
        with ctx.db.begin_nested():
            ctx.db.delete(person)
            ctx.db.flush()
    except IntegrityError:
        return False
    record_change(ctx, "delete", person)
    return True
