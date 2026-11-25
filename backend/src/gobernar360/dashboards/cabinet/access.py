"""Access dependencies of the cabinet dashboard."""

from typing import Annotated

from fastapi import Depends

from gobernar360.platform.access import AccessLevel, RequestContext, require_dashboard

KEY = "cabinet"

Viewer = Annotated[RequestContext, Depends(require_dashboard(KEY, AccessLevel.VIEWER))]
Editor = Annotated[RequestContext, Depends(require_dashboard(KEY, AccessLevel.EDITOR))]
