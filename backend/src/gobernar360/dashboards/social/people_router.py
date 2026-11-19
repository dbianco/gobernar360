"""People of the municipality's registry incorporated into the social dashboard.

The dashboard lists and opens only the people it incorporated. The rest of the
registry is reachable in one way: looking a person up by exact document number
before adding them, so the same person is not loaded twice.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import or_, select

from gobernar360.core.errors import already_registered, validation_error
from gobernar360.dashboards.social.access import Editor, Viewer
from gobernar360.dashboards.social.models import SocialPerson
from gobernar360.dashboards.social.schemas import (
    LookupOut,
    SocialPersonIn,
    SocialPersonOut,
    SocialPersonPatch,
)
from gobernar360.platform import people
from gobernar360.platform.access import RequestContext
from gobernar360.platform.listing import Page, PagingParams, SearchText, contains, page_of
from gobernar360.platform.models import Person
from gobernar360.platform.tenant_crud import create_entity, delete_entity, get_or_404

router = APIRouter()

_dni = TypeAdapter(people.Dni)


def _registered(ctx: RequestContext, person: Person) -> SocialPerson | None:
    return ctx.db.scalar(select(SocialPerson).where(SocialPerson.person_id == person.id))


@router.get("/people")
def list_people(
    ctx: Viewer,
    paging: PagingParams,
    q: SearchText = None,
    neighborhood: SearchText = None,
) -> Page[SocialPersonOut]:
    query = (
        select(SocialPerson)
        .join(Person, SocialPerson.person_id == Person.id)
        .order_by(Person.last_name, Person.first_name, SocialPerson.id)
    )
    # Every word typed must appear in the name or the document.
    for word in (q or "").split():
        matches = [contains(Person.first_name, word), contains(Person.last_name, word)]
        digits = word.replace(".", "")
        if digits.isdigit():
            matches.append(contains(Person.dni, digits))
        query = query.where(or_(*matches))
    if neighborhood and neighborhood.strip():
        query = query.where(contains(Person.neighborhood, neighborhood.strip()))
    return page_of(ctx, query, paging)


@router.get("/people/lookup")
def lookup_person(ctx: Editor, dni: Annotated[str, Query(max_length=30)]) -> LookupOut:
    """Whether the registry already has a person with this document."""
    try:
        normalised = _dni.validate_python(dni)
    except ValidationError as error:
        raise validation_error("dni must have 6 to 9 digits.") from error
    person = people.find_by_dni(ctx, normalised)
    registered = _registered(ctx, person) if person else None
    return LookupOut(person=person, registered_id=registered.id if registered else None)


@router.post("/people", status_code=201)
def create_person(payload: SocialPersonIn, ctx: Editor) -> SocialPersonOut:
    existing = people.find_by_dni(ctx, payload.person.dni) if payload.person.dni else None
    if existing is None:
        person = people.create_person(ctx, payload.person)
    elif _registered(ctx, existing):
        raise already_registered()
    else:
        # Only what was actually sent replaces the registry's data.
        person = people.update_person(ctx, existing, payload.person.model_dump(exclude_unset=True))
    registered = create_entity(ctx, SocialPerson(person_id=person.id), {"person_id": person.id})
    ctx.db.refresh(registered)
    return registered


@router.get("/people/{person_id}")
def get_person(person_id: uuid.UUID, ctx: Viewer) -> SocialPersonOut:
    return get_or_404(ctx, SocialPerson, person_id)


@router.patch("/people/{person_id}")
def update_person(person_id: uuid.UUID, payload: SocialPersonPatch, ctx: Editor) -> SocialPersonOut:
    registered = get_or_404(ctx, SocialPerson, person_id)
    common = payload.model_dump(exclude_unset=True).get("person")
    if common:
        people.update_person(ctx, registered.person, common)
    ctx.db.refresh(registered)
    return registered


@router.delete("/people/{person_id}", status_code=204)
def delete_person(person_id: uuid.UUID, ctx: Editor) -> None:
    """Take the person out of this dashboard, and out of their household with it."""
    registered = get_or_404(ctx, SocialPerson, person_id)
    person = registered.person
    delete_entity(ctx, registered)
    people.release_person(ctx, person)
