"""Access dependencies of the social dashboard."""

from typing import Annotated

from fastapi import Depends

from gobernar360.platform.access import (
    AccessLevel,
    RequestContext,
    effective_level,
    require_dashboard,
)

KEY = "social"

Viewer = Annotated[RequestContext, Depends(require_dashboard(KEY, AccessLevel.VIEWER))]
Editor = Annotated[RequestContext, Depends(require_dashboard(KEY, AccessLevel.EDITOR))]
Admin = Annotated[RequestContext, Depends(require_dashboard(KEY, AccessLevel.ADMIN))]


# The least level that sees where one household lives; those below get counts per zone.
HOUSEHOLDS_ON_MAP = AccessLevel.EDITOR


def sees_households_on_map(ctx: RequestContext) -> bool:
    """Whether the member may know the place or the zone of one household.

    Knowing that a family is assisted and where it lives exposes it to its neighbours.
    """
    return effective_level(ctx.db, ctx.membership, KEY) >= HOUSEHOLDS_ON_MAP


def reads_reserved_text(ctx: RequestContext) -> bool:
    """Whether the member may read what the team wrote about a person.

    Intervention descriptions hold sensitive detail (health, violence, family
    matters), so viewers learn that an intervention happened but not its text.
    """
    return effective_level(ctx.db, ctx.membership, KEY) >= AccessLevel.EDITOR
