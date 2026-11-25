"""Economic actors on the map."""

import uuid
from datetime import date

from pydantic import BaseModel
from sqlalchemy import ColumnElement, func

from gobernar360.dashboards.economic.models import Actor, Sector
from gobernar360.platform.access import RequestContext
from gobernar360.platform.geo.contract import LocatedRecord, ZoneGrouping, ZoneMetric
from gobernar360.platform.listing import SearchText, contains


class ActorFilters(BaseModel):
    """The filters of the actor list."""

    q: SearchText = None
    actor_type_id: uuid.UUID | None = None
    sector_id: uuid.UUID | None = None


def actor_conditions(filters: ActorFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.q and filters.q.strip():
        text = filters.q.strip()
        matches = contains(Actor.name, text)
        digits = text.replace("-", "").replace(" ", "")
        if digits.isdigit():
            matches = matches | contains(Actor.cuit, digits)
        conditions.append(matches)
    if filters.actor_type_id is not None:
        conditions.append(Actor.actor_type_id == filters.actor_type_id)
    if filters.sector_id is not None:
        conditions.append(Actor.sector_id == filters.sector_id)
    return conditions


def _conditions(
    ctx: RequestContext, today: date, filters: ActorFilters
) -> list[ColumnElement[bool]]:
    return actor_conditions(filters)


actors = LocatedRecord(
    key="actors",
    model=Actor,
    title=Actor.name,
    filters=ActorFilters,
    conditions=_conditions,
    metrics=(ZoneMetric("actors", lambda today, filters: func.count(Actor.id)),),
    grouping=ZoneGrouping("sector", Sector, Actor.sector_id == Sector.id, Sector.name),
)
