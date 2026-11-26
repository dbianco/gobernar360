"""People of the municipality's registry incorporated into the economic dashboard.

The dashboard lists and opens only the people it incorporated. The rest of the
registry is reachable in one way: looking a person up by exact document number or
CUIL before adding them, so the same person is not loaded twice.
"""

import uuid

from fastapi import APIRouter
from sqlalchemy import or_, select

from gobernar360.core.errors import already_registered
from gobernar360.dashboards.economic.access import Editor, Viewer
from gobernar360.dashboards.economic.models import Actor, ActorPerson, EconomicPerson
from gobernar360.dashboards.economic.schemas import (
    EconomicPersonIn,
    EconomicPersonOut,
    EconomicPersonPatch,
    EmploymentStatus,
    LookupOut,
    PersonDetail,
)
from gobernar360.platform import people
from gobernar360.platform.access import RequestContext
from gobernar360.platform.listing import Page, PagingParams, SearchText, contains, page_of
from gobernar360.platform.models import Person
from gobernar360.platform.tenant_crud import create_entity, delete_entity, get_or_404, update_entity

router = APIRouter()


def _registered(ctx: RequestContext, person: Person) -> EconomicPerson | None:
    return ctx.db.scalar(select(EconomicPerson).where(EconomicPerson.person_id == person.id))


@router.get("/people")
def list_people(
    ctx: Viewer,
    paging: PagingParams,
    q: SearchText = None,
    employment_status: EmploymentStatus | None = None,
) -> Page[EconomicPersonOut]:
    query = (
        select(EconomicPerson)
        .join(Person, EconomicPerson.person_id == Person.id)
        .order_by(Person.last_name, Person.first_name, EconomicPerson.id)
    )
    # Every word typed must appear in the name or the document.
    for word in (q or "").split():
        matches = [contains(Person.first_name, word), contains(Person.last_name, word)]
        digits = word.replace(".", "")
        if digits.isdigit():
            matches.append(contains(Person.dni, digits))
        query = query.where(or_(*matches))
    if employment_status is not None:
        query = query.where(EconomicPerson.employment_status == employment_status)
    return page_of(ctx, query, paging)


@router.get("/people/lookup")
def lookup_person(
    ctx: Editor, dni: people.DocumentQuery = None, cuil: people.DocumentQuery = None
) -> LookupOut:
    """Whether the registry already has a person with this document or this CUIL."""
    person = people.look_up(ctx, dni, cuil)
    registered = _registered(ctx, person) if person else None
    return LookupOut(person=person, registered_id=registered.id if registered else None)


@router.post("/people", status_code=201)
def create_person(payload: EconomicPersonIn, ctx: Editor) -> EconomicPersonOut:
    existing = people.find_same(ctx, payload.person)
    if existing is None:
        person = people.create_person(ctx, payload.person)
    elif _registered(ctx, existing):
        raise already_registered()
    else:
        # Only what was actually sent replaces the registry's data.
        person = people.update_person(ctx, existing, payload.person.model_dump(exclude_unset=True))
    own = {"employment_status": payload.employment_status, "occupation": payload.occupation}
    registered = create_entity(
        ctx, EconomicPerson(person_id=person.id, **own), own | {"person_id": person.id}
    )
    ctx.db.refresh(registered)
    return registered


@router.get("/people/{person_id}")
def get_person(person_id: uuid.UUID, ctx: Viewer) -> PersonDetail:
    registered = get_or_404(ctx, EconomicPerson, person_id)
    links = ctx.db.scalars(
        select(ActorPerson)
        .join(Actor, ActorPerson.actor_id == Actor.id)
        .where(ActorPerson.person_id == registered.id)
        .order_by(Actor.name)
    ).all()
    return PersonDetail.model_validate(
        EconomicPersonOut.model_validate(registered).model_dump() | {"actors": links},
        from_attributes=True,
    )


@router.patch("/people/{person_id}")
def update_person(
    person_id: uuid.UUID, payload: EconomicPersonPatch, ctx: Editor
) -> EconomicPersonOut:
    registered = get_or_404(ctx, EconomicPerson, person_id)
    changes = payload.model_dump(exclude_unset=True)
    common = changes.pop("person", None)
    if common:
        people.update_person(ctx, registered.person, common)
    if changes:
        update_entity(ctx, registered, changes)
    ctx.db.refresh(registered)
    return registered


@router.delete("/people/{person_id}", status_code=204)
def delete_person(person_id: uuid.UUID, ctx: Editor) -> None:
    """Take the person out of this dashboard; links to actors go with them."""
    registered = get_or_404(ctx, EconomicPerson, person_id)
    person = registered.person
    delete_entity(ctx, registered)
    people.release_person(ctx, person)
