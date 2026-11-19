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


def reads_reserved_text(ctx: RequestContext) -> bool:
    """Whether the member may read what the team wrote about a person.

    Intervention descriptions hold sensitive detail (health, violence, family
    matters), so viewers learn that an intervention happened but not its text.
    """
    return effective_level(ctx.db, ctx.membership, KEY) >= AccessLevel.EDITOR
