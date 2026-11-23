"""Benefits delivered to people.
Reading needs viewer access; loading data needs editor access."""

import uuid
from datetime import date

from fastapi import APIRouter
from sqlalchemy import ColumnElement, select

from gobernar360.dashboards.social.access import Editor, Viewer
from gobernar360.dashboards.social.models import Benefit, Delivery, SocialPerson
from gobernar360.dashboards.social.schemas import DeliveryIn, DeliveryOut, DeliveryPatch
from gobernar360.platform.api_types import Year
from gobernar360.platform.listing import Page, PagingParams, SearchText, every_word, page_of
from gobernar360.platform.models import Person
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()


def in_year(year: int) -> ColumnElement[bool]:
    return Delivery.date.between(date(year, 1, 1), date(year, 12, 31))


@router.get("/deliveries")
def list_deliveries(
    ctx: Viewer,
    paging: PagingParams,
    year: Year | None = None,
    benefit_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    household_id: uuid.UUID | None = None,
    q: SearchText = None,
) -> Page[DeliveryOut]:
    query = select(Delivery).order_by(Delivery.date.desc(), Delivery.id)
    if q and q.strip():
        # Who received it, by name or document, or what was delivered.
        query = (
            query.join(SocialPerson, Delivery.person_id == SocialPerson.id)
            .join(Person, SocialPerson.person_id == Person.id)
            .join(Benefit, Delivery.benefit_id == Benefit.id)
            .where(
                *every_word(
                    q, Person.first_name, Person.last_name, Benefit.name, document=Person.dni
                )
            )
        )
    if year is not None:
        query = query.where(in_year(year))
    if benefit_id is not None:
        query = query.where(Delivery.benefit_id == benefit_id)
    if category_id is not None:
        query = query.where(
            Delivery.benefit_id.in_(select(Benefit.id).where(Benefit.category_id == category_id))
        )
    if person_id is not None:
        query = query.where(Delivery.person_id == person_id)
    if household_id is not None:
        query = query.where(
            Delivery.person_id.in_(
                select(SocialPerson.id).where(SocialPerson.household_id == household_id)
            )
        )
    return page_of(ctx, query, paging)


@router.post("/deliveries", status_code=201)
def create_delivery(payload: DeliveryIn, ctx: Editor) -> DeliveryOut:
    resolve(ctx, Benefit, payload.benefit_id, "benefit_id")
    resolve(ctx, SocialPerson, payload.person_id, "person_id")
    delivery = create_entity(ctx, Delivery(**payload.model_dump()), payload.model_dump())
    ctx.db.refresh(delivery)
    return delivery


@router.patch("/deliveries/{delivery_id}")
def update_delivery(delivery_id: uuid.UUID, payload: DeliveryPatch, ctx: Editor) -> DeliveryOut:
    delivery = get_or_404(ctx, Delivery, delivery_id)
    update_entity(ctx, delivery, payload.model_dump(exclude_unset=True))
    ctx.db.refresh(delivery)
    return delivery


@router.delete("/deliveries/{delivery_id}", status_code=204)
def delete_delivery(delivery_id: uuid.UUID, ctx: Editor) -> None:
    delete_entity(ctx, get_or_404(ctx, Delivery, delivery_id))
