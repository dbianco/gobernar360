"""Projects as something other modules may point at."""

import uuid
from collections.abc import Collection

from sqlalchemy import func, select

from gobernar360.dashboards.projects.models import Project
from gobernar360.dashboards.registry import LinkableRecord, SubjectRecord
from gobernar360.platform.access import RequestContext
from gobernar360.platform.listing import every_word

PROJECT = "project"


def _record(project_id: uuid.UUID, name: str) -> SubjectRecord:
    return SubjectRecord(id=project_id, label=name, path=f"/d/projects/projects/{project_id}")


def _search(ctx: RequestContext, words: str, limit: int) -> list[SubjectRecord]:
    """Projects by name, those of the latest years first."""
    rows = ctx.db.execute(
        select(Project.id, Project.name)
        .where(*every_word(words, Project.name))
        .order_by(Project.year.desc(), func.unaccent(func.lower(Project.name)), Project.id)
        .limit(limit)
    )
    return [_record(*row) for row in rows]


def _describe(ctx: RequestContext, ids: Collection[uuid.UUID]) -> list[SubjectRecord]:
    rows = ctx.db.execute(select(Project.id, Project.name).where(Project.id.in_(ids)))
    return [_record(*row) for row in rows]


LINKABLE = LinkableRecord(kind=PROJECT, search=_search, describe=_describe)
