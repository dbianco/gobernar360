"""Configuración: what a municipality's administrators set for it.

Who receives notification emails, whether members may sign in with single sign-on, what
its maps show, and the municipality's own version of each email. The same routes serve the
municipality's administrators and the platform operator, as the member routes do (see
members).
"""

import html
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select

from gobernar360.core.config import get_settings
from gobernar360.core.errors import invalid_reference, map_api_key_required
from gobernar360.platform import email_templates, municipality_settings
from gobernar360.platform.access import RequestContext, require_municipality_admin
from gobernar360.platform.audit import record_change
from gobernar360.platform.clock import Today
from gobernar360.platform.email_templates import Html, Spec
from gobernar360.platform.geo import backgrounds
from gobernar360.platform.geo.background_router import BackgroundOut
from gobernar360.platform.models import (
    DEFAULT_SMALL_ZONE_THRESHOLD,
    MAX_SMALL_ZONE_THRESHOLD,
    MIN_SMALL_ZONE_THRESHOLD,
    EmailTemplate,
    Municipality,
    MunicipalitySettings,
)
from gobernar360.platform.notifications import previous_month
from gobernar360.platform.outbox import enqueue
from gobernar360.platform.schemas import Email
from gobernar360.platform.texts import format_datetime, month_name, text


class SettingsOut(BaseModel):
    notification_emails: list[str]
    sso_enabled: bool
    # Whether the platform has an identity provider configured at all.
    sso_available: bool

    small_zone_threshold: int
    map_background: str
    # Null when there is none; the background in use may not need it.
    map_api_key: str | None
    # What can be chosen.
    map_backgrounds: list[BackgroundOut]


class MapSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    small_zone_threshold: Annotated[
        int, Field(ge=MIN_SMALL_ZONE_THRESHOLD, le=MAX_SMALL_ZONE_THRESHOLD, strict=True)
    ]
    map_background: str
    # Only what keys are made of: it becomes part of an address.
    map_api_key: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._-]{1,100}$")] | None = None


class SettingsIn(BaseModel):
    notification_emails: Annotated[list[Email], Field(max_length=50)] = []
    sso_enabled: bool = False


def _out(row: MunicipalitySettings | None) -> SettingsOut:
    return SettingsOut(
        notification_emails=list(row.notification_emails) if row else [],
        sso_enabled=bool(row and row.sso_enabled),
        sso_available=get_settings().sso_enabled,
        small_zone_threshold=(row.small_zone_threshold if row else DEFAULT_SMALL_ZONE_THRESHOLD),
        map_background=backgrounds.in_use(row.map_background if row else backgrounds.DEFAULT).key,
        map_api_key=row.map_api_key if row else None,
        map_backgrounds=[BackgroundOut.model_validate(b) for b in backgrounds.BACKGROUNDS],
    )


class TemplateOut(BaseModel):
    key: str
    subject: str
    html: str
    # False while the municipality uses the default text.
    customized: bool
    variables: list[str]
    required: list[str]


class TemplateIn(BaseModel):
    subject: Annotated[str, Field(max_length=300)]
    html: Annotated[str, Field(max_length=email_templates.MAX_HTML_LENGTH)]


def _template_out(spec: Spec, template: email_templates.Template) -> TemplateOut:
    return TemplateOut(
        key=spec.key,
        subject=template.subject,
        html=template.html,
        customized=template.customized,
        variables=list(spec.variables),
        required=list(spec.required),
    )


def _own_row(ctx: RequestContext) -> MunicipalitySettings:
    """The municipality's configuration, created the first time something is set."""
    row = municipality_settings.find(ctx.db, ctx.municipality_id)
    if row is None:
        row = MunicipalitySettings(municipality_id=ctx.municipality_id)
        ctx.db.add(row)
    return row


def _stored(ctx: RequestContext, key: str) -> EmailTemplate | None:
    return ctx.db.scalar(
        select(EmailTemplate).where(
            EmailTemplate.municipality_id == ctx.municipality_id, EmailTemplate.key == key
        )
    )


def _sample(ctx: RequestContext, spec: Spec, today) -> dict[str, object]:
    """Believable values for a test email, most of them about the person asking."""
    settings = get_settings()
    item = html.escape(text("email.test.item"))
    values: dict[str, object] = {
        "name": ctx.user.full_name,
        "inviter": ctx.user.full_name,
        "municipality": ctx.db.get(Municipality, ctx.municipality_id).name,
        "link": settings.app_link("/login"),
        "expires": format_datetime(datetime.now(UTC) + timedelta(days=7)),
        "month": month_name(previous_month(today)[1]),
        "items": Html(f"<ul><li>{item}</li></ul>"),
        "account_link": settings.app_link("/account"),
    }
    return {name: values[name] for name in spec.variables}


def build_router(context: Callable[..., RequestContext]) -> APIRouter:
    """Configuration routes for whoever `context` lets through: the municipality's own
    administrators, or the platform operator acting on the municipality in the path."""
    router = APIRouter()
    SettingsContext = Annotated[RequestContext, Depends(context)]  # noqa: N806

    @router.get("/settings")
    def read_settings(ctx: SettingsContext) -> SettingsOut:
        return _out(municipality_settings.find(ctx.db, ctx.municipality_id))

    @router.put("/settings")
    def update_settings(payload: SettingsIn, ctx: SettingsContext) -> SettingsOut:
        row = _own_row(ctx)
        # Already normalised by `Email`; repeated addresses would get every email twice.
        row.notification_emails = list(dict.fromkeys(payload.notification_emails))
        row.sso_enabled = payload.sso_enabled
        row.updated_at = datetime.now(UTC)
        row.updated_by = ctx.user.id
        ctx.db.flush()
        record_change(
            ctx,
            "update",
            row,
            {"notification_emails": row.notification_emails, "sso_enabled": row.sso_enabled},
        )
        return _out(row)

    @router.put("/settings/map")
    def update_map_settings(payload: MapSettingsIn, ctx: SettingsContext) -> SettingsOut:
        """The background of the maps, and which counts per zone are too small to show."""
        chosen = backgrounds.find(payload.map_background)
        if chosen is None:
            raise invalid_reference("map_background is not one of the backgrounds offered.")
        if chosen.provider is not None and payload.map_api_key is None:
            raise map_api_key_required()
        row = _own_row(ctx)
        row.small_zone_threshold = payload.small_zone_threshold
        row.map_background = chosen.key
        # A key nobody uses is not kept.
        row.map_api_key = payload.map_api_key if chosen.provider is not None else None
        row.updated_at = datetime.now(UTC)
        row.updated_by = ctx.user.id
        ctx.db.flush()
        record_change(
            ctx,
            "update",
            row,
            {
                "small_zone_threshold": row.small_zone_threshold,
                "map_background": row.map_background,
                "map_api_key_set": row.map_api_key is not None,
            },
        )
        return _out(row)

    @router.get("/email-templates")
    def list_templates(ctx: SettingsContext) -> list[TemplateOut]:
        return [
            _template_out(spec, email_templates.load(ctx.db, ctx.municipality_id, spec.key))
            for spec in email_templates.specs()
        ]

    @router.put("/email-templates/{key}")
    def save_template(key: str, payload: TemplateIn, ctx: SettingsContext) -> TemplateOut:
        spec = email_templates.get_spec(key)
        subject, clean = email_templates.validate(spec, payload.subject, payload.html)
        row = _stored(ctx, key)
        if row is None:
            row = EmailTemplate(municipality_id=ctx.municipality_id, key=key)
            ctx.db.add(row)
        row.subject, row.html = subject, clean
        row.updated_at = datetime.now(UTC)
        row.updated_by = ctx.user.id
        ctx.db.flush()
        record_change(ctx, "update", row, {"key": key, "subject": subject})
        return _template_out(spec, email_templates.load(ctx.db, ctx.municipality_id, key))

    @router.delete("/email-templates/{key}")
    def restore_default(key: str, ctx: SettingsContext) -> TemplateOut:
        """Go back to the default text."""
        spec = email_templates.get_spec(key)
        row = _stored(ctx, key)
        if row is not None:
            record_change(ctx, "delete", row, {"key": key})
            ctx.db.delete(row)
            ctx.db.flush()
        return _template_out(spec, email_templates.default(key))

    @router.post("/email-templates/{key}/test", status_code=204)
    def send_test(key: str, payload: TemplateIn, ctx: SettingsContext, today: Today) -> None:
        """Email the text being edited, saved or not, to the administrator asking for it."""
        spec = email_templates.get_spec(key)
        subject, clean = email_templates.validate(spec, payload.subject, payload.html)
        template = email_templates.Template(key, subject, clean, True)
        rendered = email_templates.render(template, _sample(ctx, spec, today))
        prefix = text("email.test.subjectPrefix")
        enqueue(ctx.db, ctx.user.email, prefix + rendered.subject, rendered.text, rendered.html)

    return router


router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(build_router(require_municipality_admin))
