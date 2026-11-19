"""Economic actors and the people linked to them.
Reading needs viewer access; loading data needs editor access."""

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy import or_, select

from gobernar360.core.errors import conflict, not_found
from gobernar360.dashboards.economic.access import Editor, Viewer
from gobernar360.dashboards.economic.models import (
    Actor,
    ActorPerson,
    ActorType,
    EconomicPerson,
    Sector,
)
from gobernar360.dashboards.economic.schemas import (
    ActorDetail,
    ActorIn,
    ActorOut,
    ActorPatch,
    ActorPersonIn,
    ActorPersonOut,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.listing import Page, PagingParams, SearchText, contains, page_of
from gobernar360.platform.models import Person
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()


def _check_references(ctx: RequestContext, changes: dict[str, Any]) -> None:
    for field, model in (("actor_type_id", ActorType), ("sector_id", Sector)):
        if changes.get(field) is not None:
            resolve(ctx, model, changes[field], field)


@router.get("/actors")
def list_actors(
    ctx: Viewer,
    paging: PagingParams,
    q: SearchText = None,
    actor_type_id: uuid.UUID | None = None,
    sector_id: uuid.UUID | None = None,
) -> Page[ActorOut]:
    query = select(Actor).order_by(Actor.name, Actor.id)
    if q and q.strip():
        text = q.strip()
        matches = [contains(Actor.name, text)]
        digits = text.replace("-", "").replace(" ", "")
        if digits.isdigit():
            matches.append(contains(Actor.cuit, digits))
        query = query.where(or_(*matches))
    if actor_type_id is not None:
        query = query.where(Actor.actor_type_id == actor_type_id)
    if sector_id is not None:
        query = query.where(Actor.sector_id == sector_id)
    return page_of(ctx, query, paging)


def _detail(ctx: RequestContext, actor: Actor) -> ActorDetail:
    links = ctx.db.scalars(
        select(ActorPerson)
        .join(EconomicPerson, ActorPerson.person_id == EconomicPerson.id)
        .join(Person, EconomicPerson.person_id == Person.id)
        .where(ActorPerson.actor_id == actor.id)
        .order_by(Person.last_name, Person.first_name)
    ).all()
    return ActorDetail.model_validate(
        ActorOut.model_validate(actor).model_dump() | {"people": links}, from_attributes=True
    )


@router.post("/actors", status_code=201)
def create_actor(payload: ActorIn, ctx: Editor) -> ActorOut:
    _check_references(ctx, payload.model_dump())
    actor = create_entity(ctx, Actor(**payload.model_dump()), payload.model_dump())
    ctx.db.refresh(actor)
    return actor


@router.get("/actors/{actor_id}")
def get_actor(actor_id: uuid.UUID, ctx: Viewer) -> ActorDetail:
    return _detail(ctx, get_or_404(ctx, Actor, actor_id))


@router.patch("/actors/{actor_id}")
def update_actor(actor_id: uuid.UUID, payload: ActorPatch, ctx: Editor) -> ActorOut:
    actor = get_or_404(ctx, Actor, actor_id)
    changes = payload.model_dump(exclude_unset=True)
    _check_references(ctx, changes)
    update_entity(ctx, actor, changes)
    ctx.db.refresh(actor)
    return actor


@router.delete("/actors/{actor_id}", status_code=204)
def delete_actor(actor_id: uuid.UUID, ctx: Editor) -> None:
    """Links to people go with the actor; assignments keep it from being deleted."""
    delete_entity(ctx, get_or_404(ctx, Actor, actor_id))


@router.post("/actors/{actor_id}/people", status_code=201)
def link_person(actor_id: uuid.UUID, payload: ActorPersonIn, ctx: Editor) -> ActorPersonOut:
    actor = get_or_404(ctx, Actor, actor_id)
    person = resolve(ctx, EconomicPerson, payload.person_id, "person_id")
    already_linked = ctx.db.scalar(
        select(ActorPerson.id).where(
            ActorPerson.actor_id == actor.id, ActorPerson.person_id == person.id
        )
    )
    if already_linked:
        raise conflict("This person is already linked to the actor.")
    link = ActorPerson(actor_id=actor.id, person_id=person.id, role=payload.role)
    create_entity(ctx, link, payload.model_dump() | {"actor_id": actor.id})
    ctx.db.refresh(link)
    return link


@router.delete("/actors/{actor_id}/people/{link_id}", status_code=204)
def unlink_person(actor_id: uuid.UUID, link_id: uuid.UUID, ctx: Editor) -> None:
    link = get_or_404(ctx, ActorPerson, link_id)
    if link.actor_id != actor_id:
        raise not_found()
    delete_entity(ctx, link)
