"""Headline numbers and breakdowns of the social dashboard for one year."""

from datetime import date
from typing import Any

from fastapi import APIRouter
from sqlalchemy import ColumnElement, Select, extract, func, select

from gobernar360.dashboards.registry import IndicatorDefinition, SummaryIndicator
from gobernar360.dashboards.social import deliveries_router, interventions_router
from gobernar360.dashboards.social.access import Viewer
from gobernar360.dashboards.social.models import (
    Benefit,
    BenefitCategory,
    Delivery,
    Household,
    Intervention,
    InterventionType,
    SocialPerson,
)
from gobernar360.dashboards.social.schemas import (
    BenefitCount,
    MonthCount,
    NameCount,
    ReportsOut,
    SummaryOut,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.api_types import Year
from gobernar360.platform.clock import Today
from gobernar360.platform.models import Person

router = APIRouter()

# Deliveries and interventions carry their own date, so their counts can be rebuilt for
# any past day; the people and households registered are only known as they are today.
INDICATORS = (
    IndicatorDefinition("social.people", name="Personas asistidas", aggregate=True),
    IndicatorDefinition("social.households", name="Grupos familiares", aggregate=True),
    IndicatorDefinition(
        "social.deliveries_year", reconstructible=True, name="Prestaciones del año", aggregate=True
    ),
    IndicatorDefinition(
        "social.interventions_year",
        reconstructible=True,
        name="Intervenciones del año",
        aggregate=True,
    ),
)


def _count(ctx: RequestContext, model: type[Any], *conditions: ColumnElement[bool]) -> int:
    return ctx.db.scalar(select(func.count()).select_from(model).where(*conditions))


def _distinct_people(ctx: RequestContext, model: type[Any], condition: ColumnElement[bool]) -> int:
    return ctx.db.scalar(select(func.count(func.distinct(model.person_id))).where(condition))


def _name_counts(ctx: RequestContext, query: Select[Any]) -> list[NameCount]:
    return [NameCount(name=name, count=total) for name, total in ctx.db.execute(query)]


def _interventions_by_type(ctx: RequestContext, year: int) -> list[NameCount]:
    count = func.count(Intervention.id)
    return _name_counts(
        ctx,
        select(InterventionType.name, count)
        .join(InterventionType, Intervention.intervention_type_id == InterventionType.id)
        .where(interventions_router.in_year(year))
        .group_by(InterventionType.id, InterventionType.name)
        .order_by(count.desc(), InterventionType.name),
    )


def _benefit_counts(ctx: RequestContext, year: int) -> list[BenefitCount]:
    """Deliveries and units per benefit, most delivered first."""
    count = func.count(Delivery.id)
    rows = ctx.db.execute(
        select(Benefit.name, BenefitCategory.name, count, func.sum(Delivery.quantity))
        .join(Benefit, Delivery.benefit_id == Benefit.id)
        .join(BenefitCategory, Benefit.category_id == BenefitCategory.id)
        .where(deliveries_router.in_year(year))
        .group_by(Benefit.id, Benefit.name, BenefitCategory.name)
        .order_by(count.desc(), Benefit.name)
    )
    return [
        BenefitCount(benefit=benefit, category=category, deliveries=total, units=units)
        for benefit, category, total, units in rows
    ]


@router.get("/summary")
def get_year_summary(ctx: Viewer, today: Today, year: Year | None = None) -> SummaryOut:
    year = year or today.year
    delivered, intervened = deliveries_router.in_year(year), interventions_router.in_year(year)
    units = ctx.db.scalar(select(func.coalesce(func.sum(Delivery.quantity), 0)).where(delivered))
    return SummaryOut(
        year=year,
        people=_count(ctx, SocialPerson),
        households=_count(ctx, Household),
        people_with_deliveries=_distinct_people(ctx, Delivery, delivered),
        deliveries=_count(ctx, Delivery, delivered),
        units=units,
        interventions=_count(ctx, Intervention, intervened),
        people_with_interventions=_distinct_people(ctx, Intervention, intervened),
        benefits=_benefit_counts(ctx, year),
        intervention_types=_interventions_by_type(ctx, year),
    )


def _by_month(ctx: RequestContext, column: Any, condition: ColumnElement[bool]) -> list[MonthCount]:
    month = extract("month", column)
    counts = dict(
        ctx.db.execute(select(month, func.count()).where(condition).group_by(month)).all()
    )
    return [MonthCount(month=number, count=counts.get(number, 0)) for number in range(1, 13)]


@router.get("/reports")
def get_reports(ctx: Viewer, today: Today, year: Year | None = None) -> ReportsOut:
    year = year or today.year
    delivered = deliveries_router.in_year(year)
    category_count = func.count(Delivery.id)
    # People without a neighborhood are grouped apart, under None.
    neighborhood = func.nullif(Person.neighborhood, "")
    people_count = func.count(SocialPerson.id)
    delivery_count = func.count(Delivery.id)
    return ReportsOut(
        year=year,
        deliveries_by_category=_name_counts(
            ctx,
            select(BenefitCategory.name, category_count)
            .join(Benefit, Delivery.benefit_id == Benefit.id)
            .join(BenefitCategory, Benefit.category_id == BenefitCategory.id)
            .where(delivered)
            .group_by(BenefitCategory.id, BenefitCategory.name)
            .order_by(category_count.desc(), BenefitCategory.name),
        ),
        deliveries_by_month=_by_month(ctx, Delivery.date, delivered),
        interventions_by_type=_interventions_by_type(ctx, year),
        interventions_by_month=_by_month(
            ctx, Intervention.date, interventions_router.in_year(year)
        ),
        people_by_neighborhood=_name_counts(
            ctx,
            select(neighborhood, people_count)
            .select_from(SocialPerson)
            .join(Person, SocialPerson.person_id == Person.id)
            .group_by(neighborhood)
            .order_by(people_count.desc(), neighborhood),
        ),
        deliveries_by_neighborhood=_name_counts(
            ctx,
            select(neighborhood, delivery_count)
            .select_from(Delivery)
            .join(SocialPerson, Delivery.person_id == SocialPerson.id)
            .join(Person, SocialPerson.person_id == Person.id)
            .where(delivered)
            .group_by(neighborhood)
            .order_by(delivery_count.desc(), neighborhood),
        ),
    )


def get_summary(ctx: RequestContext, today: date) -> list[SummaryIndicator]:
    """Indicators as of `today`; records are those of its year up to that day."""
    start_of_year = date(today.year, 1, 1)
    counts = {
        "social.people": _count(ctx, SocialPerson),
        "social.households": _count(ctx, Household),
        "social.deliveries_year": _count(
            ctx, Delivery, Delivery.date.between(start_of_year, today)
        ),
        "social.interventions_year": _count(
            ctx, Intervention, Intervention.date.between(start_of_year, today)
        ),
    }
    if not any(counts.values()):
        return []
    return [SummaryIndicator(key, value) for key, value in counts.items()]
