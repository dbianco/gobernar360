"""Zone profile: what every dashboard the member can see has in one zone."""

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from gobernar360.dashboards import registry
from gobernar360.platform.access import Context, RequestContext, effective_levels
from gobernar360.platform.clock import Today
from gobernar360.platform.geo import aggregates, zones
from gobernar360.platform.geo.contract import LocatedRecord
from gobernar360.platform.geo.records_router import CellOut, MetricOut, cell_out
from gobernar360.platform.geo.zones_router import ZoneRef

router = APIRouter(tags=["overview"])


class ProfileSection(CellOut):
    dashboard_key: str
    record_key: str
    metrics: list[MetricOut]
    grouping: str | None
    threshold: int | None


class ZoneProfile(BaseModel):
    zone: ZoneRef
    sections: list[ProfileSection]


def _overview_filters(ctx: RequestContext, record: LocatedRecord, today: Any) -> BaseModel:
    if record.overview_filters is None:
        return record.filters()
    return record.overview_filters(ctx, today)


@router.get("/overview/zones/{zone_id}")
def get_zone_profile(zone_id: uuid.UUID, ctx: Context, today: Today) -> ZoneProfile:
    zone = zones.find(ctx.db, zone_id)
    sections = []
    for key, level in effective_levels(ctx.db, ctx.membership).items():
        for record in registry.get_module(key).located:
            # Worked out for every zone: which counts are hidden depends on the others.
            found = aggregates.by_zone(
                ctx, record, level, _overview_filters(ctx, record, today), today
            )
            cell = next(cell for other, cell in found.zones if other.id == zone.id)
            sections.append(
                ProfileSection(
                    dashboard_key=key,
                    record_key=record.key,
                    metrics=[MetricOut(key=m.key, unit=m.unit) for m in record.metrics],
                    grouping=record.grouping.key if record.grouping else None,
                    threshold=found.threshold,
                    **cell_out(cell),
                )
            )
    return ZoneProfile(zone=ZoneRef.model_validate(zone), sections=sections)
