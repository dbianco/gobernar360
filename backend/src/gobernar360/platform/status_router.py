"""Status lights of a dashboard: read by its viewers, set by its administrators."""

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from gobernar360.core.errors import forbidden, future_month
from gobernar360.platform import status
from gobernar360.platform.access import AccessLevel, Context, RequestContext, effective_level
from gobernar360.platform.api_types import OrmModel, Year
from gobernar360.platform.clock import Today
from gobernar360.platform.models import DashboardStatus
from gobernar360.platform.tenant_crud import create_entity, delete_entity, update_entity

router = APIRouter(prefix="/dashboards/{dashboard_key}/status", tags=["status"])

Color = Literal["green", "yellow", "red"]
Month = Annotated[int, Path(ge=1, le=12)]


class MonthStatusOut(OrmModel):
    month: int
    color: Color


class StatusIn(BaseModel):
    # Null leaves the month without a light.
    color: Color | None


def _require(ctx: RequestContext, dashboard_key: str, level: AccessLevel) -> None:
    # Unknown and disabled dashboards have no level, so they are refused the same way.
    if effective_level(ctx.db, ctx.membership, dashboard_key) < level:
        raise forbidden()


@router.get("")
def list_status(ctx: Context, dashboard_key: str, year: Year) -> list[MonthStatusOut]:
    _require(ctx, dashboard_key, AccessLevel.VIEWER)
    return [
        MonthStatusOut.model_validate(row) for row in status.for_year(ctx.db, dashboard_key, year)
    ]


@router.put("/{year}/{month}", status_code=204)
def set_status(
    ctx: Context,
    today: Today,
    dashboard_key: str,
    year: Annotated[Year, Path()],
    month: Month,
    body: StatusIn,
) -> Response:
    _require(ctx, dashboard_key, AccessLevel.ADMIN)
    if status.is_future(year, month, today):
        raise future_month()
    existing = status.find(ctx.db, dashboard_key, year, month)
    if body.color is None:
        if existing is not None:
            delete_entity(ctx, existing)
    elif existing is not None:
        update_entity(ctx, existing, {"color": body.color})
    else:
        fields = {"dashboard_key": dashboard_key, "year": year, "month": month, "color": body.color}
        try:
            with ctx.db.begin_nested():
                create_entity(ctx, DashboardStatus(**fields), fields)
        except IntegrityError:
            # Another administrator set the same month a moment ago: theirs exists, ours wins.
            update_entity(
                ctx, status.find(ctx.db, dashboard_key, year, month), {"color": body.color}
            )
    return Response(status_code=204)
