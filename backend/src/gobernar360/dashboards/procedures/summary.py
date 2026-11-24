"""Headline numbers of the inventory and the interoperability opportunities report.

Everything here counts only the procedures currently offered.
"""

import uuid
from datetime import date

from fastapi import APIRouter
from sqlalchemy import func, select

from gobernar360.dashboards.procedures.access import Viewer
from gobernar360.dashboards.procedures.models import (
    CHANNELS,
    SOURCE_LEVELS,
    Area,
    Procedure,
    ProcedureRequirement,
    Requirement,
    Source,
)
from gobernar360.dashboards.procedures.schemas import (
    ChannelCount,
    NameCount,
    OpportunitiesOut,
    Reach,
    RequirementCount,
    SourceOpportunity,
    SummaryOut,
)
from gobernar360.dashboards.registry import IndicatorDefinition, SummaryIndicator
from gobernar360.platform.access import RequestContext

router = APIRouter()

TOP_REQUIREMENTS = 10
ONLINE_CHANNELS = ("online", "both")
ACTIVE = Procedure.is_active.is_(True)

# The inventory is kept as it stands today, with no record of when a procedure went
# online or stopped being offered, so none of these can be rebuilt for a past month.
INDICATORS = (
    IndicatorDefinition("procedures.active", name="Trámites vigentes", aggregate=True),
    IndicatorDefinition("procedures.online", name="Trámites en línea", aggregate=True),
    IndicatorDefinition(
        "procedures.online_ratio", "ratio", name="Trámites con canal en línea", aggregate=True
    ),
    # Every requirement is something a person has to bring or the municipality to fetch.
    IndicatorDefinition(
        "procedures.requirements",
        higher_is_better=False,
        name="Requisitos cargados",
        aggregate=True,
    ),
    IndicatorDefinition("procedures.sources", name="Fuentes cargadas", aggregate=True),
)


def summary_of(ctx: RequestContext) -> SummaryOut:
    by_channel = dict(
        ctx.db.execute(
            select(Procedure.channel, func.count()).where(ACTIVE).group_by(Procedure.channel)
        ).all()
    )
    procedures = sum(by_channel.values())
    area_count = func.count(Procedure.id)
    by_area = ctx.db.execute(
        select(Area.name, area_count)
        .join(Procedure, Procedure.area_id == Area.id)
        .where(ACTIVE)
        .group_by(Area.id, Area.name)
        .order_by(area_count.desc(), Area.name)
    )
    asked = (
        select(ProcedureRequirement.requirement_id, func.count().label("times"))
        .join(Procedure, ProcedureRequirement.procedure_id == Procedure.id)
        .where(ACTIVE)
        .group_by(ProcedureRequirement.requirement_id)
        .subquery()
    )
    links = ctx.db.scalar(select(func.coalesce(func.sum(asked.c.times), 0)))
    top = ctx.db.execute(
        select(Requirement.name, Source.name, asked.c.times)
        .join(asked, asked.c.requirement_id == Requirement.id)
        .outerjoin(Source, Requirement.source_id == Source.id)
        .order_by(asked.c.times.desc(), Requirement.name, Requirement.id)
        .limit(TOP_REQUIREMENTS)
    )
    return SummaryOut(
        procedures=procedures,
        online=sum(by_channel.get(channel, 0) for channel in ONLINE_CHANNELS),
        average_requirements=round(links / procedures, 1) if procedures else None,
        requirements=ctx.db.scalar(select(func.count()).select_from(Requirement)),
        sources=ctx.db.scalar(select(func.count()).select_from(Source)),
        by_area=[NameCount(name=name, count=count) for name, count in by_area],
        by_channel=[
            ChannelCount(channel=channel, count=by_channel.get(channel, 0)) for channel in CHANNELS
        ],
        top_requirements=[
            RequirementCount(name=name, source=source, count=count) for name, source, count in top
        ],
    )


@router.get("/summary")
def get_dashboard_summary(ctx: Viewer) -> SummaryOut:
    return summary_of(ctx)


def _reach(rows: list[tuple[uuid.UUID, uuid.UUID, int | None]]) -> Reach:
    """Reach of (requirement, procedure, volume) rows; a procedure's volume counts once."""
    volumes = {procedure_id: volume or 0 for _, procedure_id, volume in rows}
    return Reach(
        requirements=len({requirement_id for requirement_id, _, _ in rows}),
        procedures=len(volumes),
        annual_volume=sum(volumes.values()),
    )


def opportunities_of(ctx: RequestContext) -> OpportunitiesOut:
    asked = ctx.db.execute(
        select(
            Requirement.source_id,
            Requirement.id,
            Procedure.id,
            Procedure.annual_volume,
        )
        .join(ProcedureRequirement, ProcedureRequirement.requirement_id == Requirement.id)
        .join(Procedure, ProcedureRequirement.procedure_id == Procedure.id)
        .where(ACTIVE)
    ).all()
    by_source: dict[uuid.UUID | None, list[tuple[uuid.UUID, uuid.UUID, int | None]]] = {}
    for source_id, *row in asked:
        by_source.setdefault(source_id, []).append(tuple(row))
    without_source = _reach(by_source.pop(None, []))
    sources = ctx.db.scalars(select(Source).where(Source.id.in_(by_source))).all()
    rows = [
        SourceOpportunity(source=source, **_reach(by_source[source.id]).model_dump())
        for source in sources
    ]
    # Closest to home first: data the municipality itself already holds.
    rows.sort(
        key=lambda row: (
            SOURCE_LEVELS.index(row.source.level),
            -row.annual_volume,
            -row.procedures,
            row.source.name,
        )
    )
    return OpportunitiesOut(sources=rows, without_source=without_source)


@router.get("/opportunities")
def get_opportunities(ctx: Viewer) -> OpportunitiesOut:
    return opportunities_of(ctx)


def get_summary(ctx: RequestContext, today: date) -> list[SummaryIndicator]:
    """Indicators for the general overview."""
    summary = summary_of(ctx)
    if not (summary.procedures or summary.requirements or summary.sources):
        return []
    online_ratio = summary.online / summary.procedures if summary.procedures else None
    return [
        SummaryIndicator("procedures.active", summary.procedures),
        SummaryIndicator("procedures.online", summary.online),
        SummaryIndicator("procedures.online_ratio", online_ratio, "ratio"),
        SummaryIndicator("procedures.requirements", summary.requirements),
        SummaryIndicator("procedures.sources", summary.sources),
    ]
