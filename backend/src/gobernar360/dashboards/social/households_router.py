"""Households (family groups) and their members.
Reading needs viewer access; loading data needs editor access."""

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy import case, func, or_, select

from gobernar360.core.errors import household_has_head, in_another_household, not_found
from gobernar360.dashboards.social.access import Editor, Viewer
from gobernar360.dashboards.social.models import Household, SocialPerson
from gobernar360.dashboards.social.schemas import (
    HouseholdDetail,
    HouseholdIn,
    HouseholdOut,
    HouseholdPatch,
    MemberIn,
    PersonRef,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.listing import Page, PagingParams, SearchText, contains, page_of
from gobernar360.platform.models import Person
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    update_entity,
)

router = APIRouter()

HEAD = "head"


def _members(ctx: RequestContext, household_ids: list[uuid.UUID]) -> list[SocialPerson]:
    """Members of the given households: the head first, the rest by name."""
    if not household_ids:
        return []
    return (
        ctx.db.scalars(
            select(SocialPerson)
            .join(Person, SocialPerson.person_id == Person.id)
            .where(SocialPerson.household_id.in_(household_ids))
            .order_by(
                case((SocialPerson.relationship == HEAD, 0), else_=1),
                Person.last_name,
                Person.first_name,
                SocialPerson.id,
            )
        )
        .unique()
        .all()
    )


def _summaries(ctx: RequestContext, households: list[Household]) -> list[dict[str, Any]]:
    by_household: dict[uuid.UUID, list[SocialPerson]] = {h.id: [] for h in households}
    for member in _members(ctx, list(by_household)):
        by_household[member.household_id].append(member)
    summaries = []
    for household in households:
        members = by_household[household.id]
        head = next((m for m in members if m.relationship == HEAD), None)
        summaries.append(
            {
                "id": household.id,
                "name": household.name,
                "address": household.address,
                "neighborhood": household.neighborhood,
                "member_count": len(members),
                "head": PersonRef.model_validate(head) if head else None,
                "members": members,
            }
        )
    return summaries


def _detail(ctx: RequestContext, household: Household) -> dict[str, Any]:
    return _summaries(ctx, [household])[0]


@router.get("/households")
def list_households(ctx: Viewer, paging: PagingParams, q: SearchText = None) -> Page[HouseholdOut]:
    query = select(Household).order_by(func.unaccent(Household.name), Household.id)
    for word in (q or "").split():
        query = query.where(or_(contains(Household.name, word), contains(Household.address, word)))
    page = page_of(ctx, query, paging)
    return {"items": _summaries(ctx, page["items"]), "total": page["total"]}


@router.post("/households", status_code=201)
def create_household(payload: HouseholdIn, ctx: Editor) -> HouseholdOut:
    household = create_entity(ctx, Household(**payload.model_dump()), payload.model_dump())
    return _detail(ctx, household)


@router.get("/households/{household_id}")
def get_household(household_id: uuid.UUID, ctx: Viewer) -> HouseholdDetail:
    return _detail(ctx, get_or_404(ctx, Household, household_id))


@router.patch("/households/{household_id}")
def update_household(household_id: uuid.UUID, payload: HouseholdPatch, ctx: Editor) -> HouseholdOut:
    household = get_or_404(ctx, Household, household_id)
    update_entity(ctx, household, payload.model_dump(exclude_unset=True))
    return _detail(ctx, household)


@router.delete("/households/{household_id}", status_code=204)
def delete_household(household_id: uuid.UUID, ctx: Editor) -> None:
    """Delete the group; its members stay in the dashboard without a household."""
    household = get_or_404(ctx, Household, household_id)
    for member in _members(ctx, [household.id]):
        update_entity(ctx, member, {"household_id": None, "relationship": None})
    delete_entity(ctx, household)


@router.put("/households/{household_id}/members/{person_id}")
def set_member(
    household_id: uuid.UUID, person_id: uuid.UUID, payload: MemberIn, ctx: Editor
) -> HouseholdDetail:
    """Add a person to the household, or change what they are within it."""
    household = get_or_404(ctx, Household, household_id)
    person = get_or_404(ctx, SocialPerson, person_id)
    if person.household_id not in (None, household.id):
        raise in_another_household()
    if payload.relationship == HEAD:
        current_head = ctx.db.scalar(
            select(SocialPerson.id).where(
                SocialPerson.household_id == household.id,
                SocialPerson.relationship == HEAD,
                SocialPerson.id != person.id,
            )
        )
        if current_head is not None:
            raise household_has_head()
    update_entity(ctx, person, {"household_id": household.id, "relationship": payload.relationship})
    return _detail(ctx, household)


@router.delete("/households/{household_id}/members/{person_id}", status_code=204)
def remove_member(household_id: uuid.UUID, person_id: uuid.UUID, ctx: Editor) -> None:
    household = get_or_404(ctx, Household, household_id)
    person = get_or_404(ctx, SocialPerson, person_id)
    if person.household_id != household.id:
        raise not_found()
    update_entity(ctx, person, {"household_id": None, "relationship": None})
