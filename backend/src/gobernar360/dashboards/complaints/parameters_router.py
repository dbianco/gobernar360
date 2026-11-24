"""Areas, zones, complaint types and the working calendar.

Everyone with access reads them; only dashboard admins change them.
"""

import uuid

from fastapi import APIRouter
from sqlalchemy import func, select

from gobernar360.core.errors import conflict
from gobernar360.dashboards.complaints.access import Admin, Viewer
from gobernar360.dashboards.complaints.clock import MONDAY_TO_FRIDAY
from gobernar360.dashboards.complaints.models import (
    Area,
    ComplaintType,
    Holiday,
    WorkingWeek,
    Zone,
)
from gobernar360.dashboards.complaints.schemas import (
    CalendarOut,
    HolidayIn,
    HolidayOut,
    NamedRef,
    NameIn,
    TypeIn,
    TypeOut,
    TypePatch,
    WorkingWeekIn,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()


def _by_name(model):
    return (func.unaccent(func.lower(model.name)), model.id)


def _named_catalog(path: str, model: type[Area] | type[Zone]) -> None:
    """List, add, rename and delete for a catalog that only has a name."""

    @router.get(f"/{path}", name=f"list_{path}")
    def list_items(ctx: Viewer) -> list[NamedRef]:
        return ctx.db.scalars(select(model).order_by(*_by_name(model))).all()

    @router.post(f"/{path}", status_code=201, name=f"create_{path}")
    def create_item(payload: NameIn, ctx: Admin) -> NamedRef:
        return create_entity(ctx, model(name=payload.name), payload.model_dump())

    @router.patch(f"/{path}/{{item_id}}", name=f"rename_{path}")
    def rename_item(item_id: uuid.UUID, payload: NameIn, ctx: Admin) -> NamedRef:
        return update_entity(ctx, get_or_404(ctx, model, item_id), payload.model_dump())

    @router.delete(f"/{path}/{{item_id}}", status_code=204, name=f"delete_{path}")
    def delete_item(item_id: uuid.UUID, ctx: Admin) -> None:
        """Refused with 409 in_use while a type, complaint or timeline entry refers to it."""
        delete_entity(ctx, get_or_404(ctx, model, item_id))


_named_catalog("areas", Area)
_named_catalog("zones", Zone)


@router.get("/types")
def list_types(ctx: Viewer) -> list[TypeOut]:
    return ctx.db.scalars(select(ComplaintType).order_by(*_by_name(ComplaintType))).all()


def _present_type(ctx: RequestContext, complaint_type: ComplaintType) -> ComplaintType:
    ctx.db.refresh(complaint_type)
    return complaint_type


@router.post("/types", status_code=201)
def create_type(payload: TypeIn, ctx: Admin) -> TypeOut:
    resolve(ctx, Area, payload.area_id, "area_id")
    created = create_entity(ctx, ComplaintType(**payload.model_dump()), payload.model_dump())
    return _present_type(ctx, created)


@router.patch("/types/{type_id}")
def update_type(type_id: uuid.UUID, payload: TypePatch, ctx: Admin) -> TypeOut:
    """A new target applies to complaints registered from now on, not to earlier ones."""
    complaint_type = get_or_404(ctx, ComplaintType, type_id)
    changes = payload.model_dump(exclude_unset=True)
    if "area_id" in changes:
        resolve(ctx, Area, changes["area_id"], "area_id")
    return _present_type(ctx, update_entity(ctx, complaint_type, changes))


@router.delete("/types/{type_id}", status_code=204)
def delete_type(type_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, ComplaintType, type_id))


def _calendar(ctx: RequestContext) -> CalendarOut:
    week = ctx.db.scalar(select(WorkingWeek.weekdays))
    holidays = ctx.db.scalars(select(Holiday).order_by(Holiday.date)).all()
    return CalendarOut(
        weekdays=sorted(week) if week else sorted(MONDAY_TO_FRIDAY),
        holidays=[HolidayOut.model_validate(holiday) for holiday in holidays],
    )


@router.get("/calendar")
def get_calendar(ctx: Viewer) -> CalendarOut:
    return _calendar(ctx)


@router.put("/calendar/weekdays")
def set_working_weekdays(payload: WorkingWeekIn, ctx: Admin) -> CalendarOut:
    weekdays = sorted(set(payload.weekdays))
    week = ctx.db.scalar(select(WorkingWeek))
    if week is None:
        create_entity(ctx, WorkingWeek(weekdays=weekdays), {"weekdays": weekdays})
    else:
        update_entity(ctx, week, {"weekdays": weekdays})
    return _calendar(ctx)


@router.post("/calendar/holidays", status_code=201)
def add_holiday(payload: HolidayIn, ctx: Admin) -> HolidayOut:
    if ctx.db.scalar(select(Holiday.id).where(Holiday.date == payload.date)):
        raise conflict("That date is already a holiday.")
    return create_entity(ctx, Holiday(**payload.model_dump()), payload.model_dump())


@router.delete("/calendar/holidays/{holiday_id}", status_code=204)
def delete_holiday(holiday_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Holiday, holiday_id))
