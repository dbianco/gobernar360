"""Headline numbers and breakdowns of the economic dashboard for one year."""

from datetime import date
from typing import Any

from fastapi import APIRouter
from sqlalchemy import ColumnElement, extract, func, select

from gobernar360.dashboards.economic.access import Viewer
from gobernar360.dashboards.economic.assignments_router import in_year
from gobernar360.dashboards.economic.models import (
    EMPLOYMENT_STATUSES,
    Actor,
    ActorType,
    Assignment,
    EconomicPerson,
    Sector,
    Tool,
    ToolCategory,
)
from gobernar360.dashboards.economic.schemas import (
    MonthCount,
    NameCount,
    RecipientCount,
    ReportsOut,
    StatusCount,
    SummaryOut,
    ToolCount,
)
from gobernar360.dashboards.registry import IndicatorDefinition, SummaryIndicator
from gobernar360.platform.access import RequestContext
from gobernar360.platform.api_types import Year
from gobernar360.platform.clock import Today

router = APIRouter()

# Assignments carry their own date, so their count can be rebuilt for any past day; the
# actors, people and tools registered are only known as they are today.
INDICATORS = (
    IndicatorDefinition("economic.actors", name="Actores económicos", aggregate=True),
    IndicatorDefinition("economic.people", name="Personas registradas", aggregate=True),
    IndicatorDefinition("economic.tools", name="Herramientas de apoyo", aggregate=True),
    IndicatorDefinition(
        "economic.assignments_year",
        reconstructible=True,
        name="Asignaciones del año",
        aggregate=True,
    ),
)


def _count(ctx: RequestContext, model: type[Any], *conditions: ColumnElement[bool]) -> int:
    return ctx.db.scalar(select(func.count()).select_from(model).where(*conditions))


def _recipients(ctx: RequestContext, model: type[Any], target: Any, year: int) -> RecipientCount:
    with_assignments = ctx.db.scalar(
        select(func.count(func.distinct(target))).where(target.is_not(None), in_year(year))
    )
    return RecipientCount(total=_count(ctx, model), with_assignments=with_assignments)


def _tool_counts(ctx: RequestContext, target: Any, year: int) -> list[ToolCount]:
    """Assignments per tool to one kind of recipient, most assigned first."""
    count = func.count(Assignment.id)
    rows = ctx.db.execute(
        select(Tool.name, ToolCategory.name, count)
        .join(Tool, Assignment.tool_id == Tool.id)
        .join(ToolCategory, Tool.category_id == ToolCategory.id)
        .where(target.is_not(None), in_year(year))
        .group_by(Tool.id, Tool.name, ToolCategory.name)
        .order_by(count.desc(), Tool.name)
    )
    return [ToolCount(tool=tool, category=category, count=total) for tool, category, total in rows]


def summary_of_year(ctx: RequestContext, year: int) -> SummaryOut:
    return SummaryOut(
        year=year,
        actors=_recipients(ctx, Actor, Assignment.actor_id, year),
        people=_recipients(ctx, EconomicPerson, Assignment.person_id, year),
        tools=_count(ctx, Tool),
        assignments=_count(ctx, Assignment, in_year(year)),
        actor_tools=_tool_counts(ctx, Assignment.actor_id, year),
        person_tools=_tool_counts(ctx, Assignment.person_id, year),
    )


@router.get("/summary")
def get_year_summary(ctx: Viewer, today: Today, year: Year | None = None) -> SummaryOut:
    return summary_of_year(ctx, year or today.year)


def _actors_by(ctx: RequestContext, dimension: type[Any], foreign_key: Any) -> list[NameCount]:
    """Actors per value of an optional list; those without a value come under None."""
    count = func.count(Actor.id)
    rows = ctx.db.execute(
        select(dimension.name, count)
        .select_from(Actor)
        .outerjoin(dimension, foreign_key == dimension.id)
        .group_by(dimension.id, dimension.name)
        .order_by(count.desc(), dimension.name)
    )
    return [NameCount(name=name, count=total) for name, total in rows]


@router.get("/reports")
def get_reports(ctx: Viewer, today: Today, year: Year | None = None) -> ReportsOut:
    year = year or today.year
    by_status = dict(
        ctx.db.execute(
            select(EconomicPerson.employment_status, func.count()).group_by(
                EconomicPerson.employment_status
            )
        ).all()
    )
    category_count = func.count(Assignment.id)
    by_category = ctx.db.execute(
        select(ToolCategory.name, category_count)
        .join(Tool, Assignment.tool_id == Tool.id)
        .join(ToolCategory, Tool.category_id == ToolCategory.id)
        .where(in_year(year))
        .group_by(ToolCategory.id, ToolCategory.name)
        .order_by(category_count.desc(), ToolCategory.name)
    )
    month = extract("month", Assignment.date)
    by_month = dict(
        ctx.db.execute(select(month, func.count()).where(in_year(year)).group_by(month)).all()
    )
    return ReportsOut(
        year=year,
        actors_by_type=_actors_by(ctx, ActorType, Actor.actor_type_id),
        actors_by_sector=_actors_by(ctx, Sector, Actor.sector_id),
        people_by_employment_status=[
            StatusCount(status=status, count=by_status[status])
            for status in sorted(
                by_status, key=lambda s: (-by_status[s], EMPLOYMENT_STATUSES.index(s))
            )
        ],
        assignments_by_category=[NameCount(name=name, count=total) for name, total in by_category],
        assignments_by_month=[
            MonthCount(month=number, count=by_month.get(number, 0)) for number in range(1, 13)
        ],
    )


def get_summary(ctx: RequestContext, today: date) -> list[SummaryIndicator]:
    """Indicators as of `today`; assignments are those of its year up to that day."""
    so_far_this_year = Assignment.date.between(date(today.year, 1, 1), today)
    counts = {
        "economic.actors": _count(ctx, Actor),
        "economic.people": _count(ctx, EconomicPerson),
        "economic.tools": _count(ctx, Tool),
        "economic.assignments_year": _count(ctx, Assignment, so_far_this_year),
    }
    if not any(counts.values()):
        return []
    return [SummaryIndicator(key, value) for key, value in counts.items()]
