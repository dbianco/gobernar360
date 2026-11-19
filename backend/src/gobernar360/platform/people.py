"""The municipality's registry of people, shared by the dashboards that work with residents.

It has no routes of its own: each dashboard reaches the registry through these
helpers and decides which people it shows. A dashboard may only look a person up
by exact document number, so it never browses people it did not incorporate.
"""

import re
import uuid
from datetime import date
from typing import Annotated, Any, ClassVar

from pydantic import AfterValidator, BaseModel, BeforeValidator, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from gobernar360.core.errors import dni_exists
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
    birth_date: date | None = None
    phone: Phone = ""
    email: Email = ""
    address: Address = ""
    neighborhood: Neighborhood = ""


class PersonPatch(PatchModel):
    nullable: ClassVar[frozenset[str]] = frozenset({"dni", "birth_date"})

    first_name: PersonName | None = None
    last_name: PersonName | None = None
    dni: Annotated[Dni | None, BeforeValidator(_strip_dni)] = None
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
    birth_date: date | None
    phone: str
    email: str
    address: str
    neighborhood: str


def find_by_dni(ctx: RequestContext, dni: str) -> Person | None:
    return ctx.db.scalar(select(Person).where(Person.dni == dni))


def _ensure_dni_is_free(ctx: RequestContext, dni: str | None, person: Person | None) -> None:
    if dni is None:
        return
    holder = find_by_dni(ctx, dni)
    if holder is not None and (person is None or holder.id != person.id):
        raise dni_exists()


def create_person(ctx: RequestContext, data: PersonIn) -> Person:
    _ensure_dni_is_free(ctx, data.dni, None)
    return create_entity(ctx, Person(**data.model_dump()), data.model_dump())


def update_person(ctx: RequestContext, person: Person, changes: dict[str, Any]) -> Person:
    """Apply the given fields; an empty set of changes leaves no trace."""
    if not changes:
        return person
    if "dni" in changes:
        _ensure_dni_is_free(ctx, changes["dni"], person)
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
