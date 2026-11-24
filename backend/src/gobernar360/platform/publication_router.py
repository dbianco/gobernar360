"""What the municipality shows on its public page; set by municipality admins.

Every change rewrites the published copies in the same transaction, so it is on the
public page, or gone from it, as soon as the request ends.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, BeforeValidator, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from gobernar360.core.errors import dashboard_not_published, not_aggregate, not_found, slug_taken
from gobernar360.dashboards import registry
from gobernar360.platform import publication
from gobernar360.platform.access import (
    RequestContext,
    enabled_dashboard_keys,
    require_municipality_admin,
)
from gobernar360.platform.clock import Today
from gobernar360.platform.models import (
    Municipality,
    PublicSettings,
    PublishedDashboard,
    PublishedIndicator,
)
from gobernar360.platform.tenant_crud import create_entity, delete_entity, update_entity

router = APIRouter(prefix="/publication", tags=["publication"])

Admin = Annotated[RequestContext, Depends(require_municipality_admin)]
DEFAULT_THRESHOLD = 5
# Lower-case words joined by hyphens, as typed or pasted: "  Noetinger " is "noetinger".
Slug = Annotated[
    str,
    BeforeValidator(lambda value: value.strip().lower() if isinstance(value, str) else value),
    StringConstraints(min_length=3, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$"),
]


class IndicatorChoice(BaseModel):
    key: str
    name: str
    unit: str | None
    # Only aggregate indicators can be published.
    aggregate: bool
    published: bool


class DashboardChoice(BaseModel):
    key: str
    name: str
    published: bool
    indicators: list[IndicatorChoice]


class PublicationOut(BaseModel):
    enabled: bool
    slug: str
    small_count_threshold: int
    dashboards: list[DashboardChoice]


class SettingsIn(BaseModel):
    enabled: bool
    slug: Slug
    small_count_threshold: int = Field(ge=0, le=1000)


class PublishIn(BaseModel):
    published: bool


def _state(ctx: RequestContext) -> PublicationOut:
    settings = publication.settings_of(ctx)
    dashboards = set(ctx.db.scalars(select(PublishedDashboard.dashboard_key)))
    chosen = set(ctx.db.scalars(select(PublishedIndicator.indicator_key)))
    enabled = enabled_dashboard_keys(ctx.db, ctx.municipality_id)
    return PublicationOut(
        enabled=settings.enabled if settings else False,
        slug=settings.slug if settings else ctx.db.get(Municipality, ctx.municipality_id).slug,
        small_count_threshold=settings.small_count_threshold if settings else DEFAULT_THRESHOLD,
        dashboards=[
            DashboardChoice(
                key=module.key,
                name=module.name or module.key,
                published=module.key in dashboards,
                indicators=[
                    IndicatorChoice(
                        key=definition.key,
                        name=definition.display_name,
                        unit=definition.unit,
                        aggregate=definition.aggregate,
                        published=definition.key in chosen,
                    )
                    for definition in module.indicators
                ],
            )
            for module in registry.all_modules()
            if module.key in enabled
        ],
    )


@router.get("")
def get_publication(ctx: Admin) -> PublicationOut:
    return _state(ctx)


@router.put("/settings")
def set_settings(ctx: Admin, today: Today, body: SettingsIn) -> PublicationOut:
    """Turn the page on or off, choose its address and the small-count threshold."""
    settings = publication.settings_of(ctx)
    fields = body.model_dump()
    try:
        with ctx.db.begin_nested():
            if settings is None:
                create_entity(ctx, PublicSettings(**fields), fields)
            else:
                update_entity(ctx, settings, fields)
    except IntegrityError as error:
        # Only the address is unique across municipalities.
        raise slug_taken() from error
    publication.refresh_site(ctx, today)
    return _state(ctx)


def _enabled_module(ctx: RequestContext, key: str) -> registry.DashboardModule:
    module = registry.get_module(key)
    if module is None or key not in enabled_dashboard_keys(ctx.db, ctx.municipality_id):
        raise not_found("The municipality has no such dashboard.")
    return module


@router.put("/dashboards/{dashboard_key}")
def publish_dashboard(
    ctx: Admin, today: Today, dashboard_key: str, body: PublishIn
) -> PublicationOut:
    """Show a dashboard's lights; unpublishing it also unpublishes its indicators."""
    _enabled_module(ctx, dashboard_key)
    row = ctx.db.scalar(
        select(PublishedDashboard).where(PublishedDashboard.dashboard_key == dashboard_key)
    )
    if body.published and row is None:
        fields = {"dashboard_key": dashboard_key}
        create_entity(ctx, PublishedDashboard(**fields), fields)
    elif not body.published and row is not None:
        for indicator in ctx.db.scalars(
            select(PublishedIndicator).where(PublishedIndicator.dashboard_key == dashboard_key)
        ):
            delete_entity(ctx, indicator)
        delete_entity(ctx, row)
    publication.refresh_site(ctx, today)
    return _state(ctx)


@router.put("/indicators/{indicator_key}")
def publish_indicator(
    ctx: Admin, today: Today, indicator_key: str, body: PublishIn
) -> PublicationOut:
    """Show an indicator of a published dashboard; only aggregate ones can be."""
    found = registry.find_indicator(indicator_key)
    if found is None:
        raise not_found("No dashboard has an indicator with that key.")
    module, definition = found
    _enabled_module(ctx, module.key)
    row = ctx.db.scalar(
        select(PublishedIndicator).where(PublishedIndicator.indicator_key == indicator_key)
    )
    if body.published and row is None:
        if not definition.aggregate:
            raise not_aggregate()
        published_dashboard = ctx.db.scalar(
            select(PublishedDashboard.id).where(PublishedDashboard.dashboard_key == module.key)
        )
        if published_dashboard is None:
            raise dashboard_not_published()
        fields = {"dashboard_key": module.key, "indicator_key": indicator_key}
        create_entity(ctx, PublishedIndicator(**fields), fields)
    elif not body.published and row is not None:
        delete_entity(ctx, row)
    publication.refresh_site(ctx, today)
    return _state(ctx)
