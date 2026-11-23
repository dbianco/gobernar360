"""The signed-in user's choice of email notifications."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import delete, select

from gobernar360.core.errors import not_found
from gobernar360.platform.access import CurrentUser, Db
from gobernar360.platform.models import NotificationOptOut
from gobernar360.platform.notifications import all_kinds

router = APIRouter(prefix="/auth/notifications", tags=["auth"])


class NotificationSetting(BaseModel):
    kind: str
    enabled: bool


class NotificationSettingIn(BaseModel):
    enabled: bool


@router.get("")
def list_settings(db: Db, user: CurrentUser) -> list[NotificationSetting]:
    """Every kind of notification, all on unless the user turned it off."""
    off = set(
        db.scalars(select(NotificationOptOut.kind).where(NotificationOptOut.user_id == user.id))
    )
    return [NotificationSetting(kind=kind, enabled=kind not in off) for kind in all_kinds()]


@router.put("/{kind}")
def update_setting(
    kind: str, payload: NotificationSettingIn, db: Db, user: CurrentUser
) -> NotificationSetting:
    if kind not in all_kinds():
        raise not_found("Unknown kind of notification.")
    db.execute(
        delete(NotificationOptOut).where(
            NotificationOptOut.user_id == user.id, NotificationOptOut.kind == kind
        )
    )
    if not payload.enabled:
        db.add(NotificationOptOut(user_id=user.id, kind=kind))
    db.flush()
    return NotificationSetting(kind=kind, enabled=payload.enabled)
