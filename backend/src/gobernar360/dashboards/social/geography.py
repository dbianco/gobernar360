"""Social households on the map. Where a family lives is shown to editors and above only."""

from datetime import date

from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, or_, select

from gobernar360.dashboards.social import deliveries_router, interventions_router
from gobernar360.dashboards.social.access import HOUSEHOLDS_ON_MAP
from gobernar360.dashboards.social.models import (
    Delivery,
    Household,
    Intervention,
    SocialPerson,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.api_types import Year
from gobernar360.platform.geo.contract import LocatedRecord, ZoneMetric
from gobernar360.platform.listing import SearchText, contains


class HouseholdFilters(BaseModel):
    """The search of the household list, and the year its help is counted for."""

    q: SearchText = None
    year: Year | None = None


def household_conditions(q: str | None) -> list[ColumnElement[bool]]:
    return [
        or_(contains(Household.name, word), contains(Household.address, word))
        for word in (q or "").split()
    ]


def _conditions(
    ctx: RequestContext, today: date, filters: HouseholdFilters
) -> list[ColumnElement[bool]]:
    return household_conditions(filters.q)


def _assisted(today: date, filters: HouseholdFilters) -> ColumnElement[int]:
    """Households with a delivery or an intervention for one of their members in the year."""
    year = filters.year or today.year
    helped = [
        select(SocialPerson.household_id)
        .join(record, record.person_id == SocialPerson.id)
        .where(SocialPerson.household_id.is_not(None), in_year)
        for record, in_year in (
            (Delivery, deliveries_router.in_year(year)),
            (Intervention, interventions_router.in_year(year)),
        )
    ]
    return func.count(Household.id).filter(or_(*(Household.id.in_(query) for query in helped)))


households = LocatedRecord(
    key="households",
    model=Household,
    title=Household.name,
    filters=HouseholdFilters,
    conditions=_conditions,
    metrics=(
        ZoneMetric("households", lambda today, filters: func.count(Household.id)),
        ZoneMetric("assisted", _assisted),
    ),
    individual_level=HOUSEHOLDS_ON_MAP,
)
