"""Commitments: who may see each one, who may change it, and who is told what.

Any member may give one to any other, or to themselves, and attach more people to be told
when it is done. Those recorded by a dashboard (`source`, e.g. a cabinet meeting) are also
that dashboard's:

- **Seen** by whoever owes it and whoever is attached; an informal one also by its creator,
  one with a source by the members with access to that dashboard. Nobody else, administrators
  included, learns that it exists.
- **Done**, said by whoever owes it (or the source's editors).
- **Owner, date and people attached**, changed by whoever owes it, the creator of an informal
  one or the source's editors. Every change of owner or date is in its history.
- **Text and link, dropping and reopening**: the creator of an informal one, or the source's
  editors. The text of one with a source belongs to that dashboard's own rules (minutes that
  close), so it is only changed through it.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, case, delete, func, or_, select, update

from gobernar360.core.errors import (
    commitment_finished,
    forbidden,
    not_found,
    validation_error,
)
from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import CommitmentOrigin
from gobernar360.platform import directory, subjects
from gobernar360.platform.access import AccessLevel, RequestContext, effective_levels
from gobernar360.platform.commitment_models import (
    Commitment,
    CommitmentEntry,
    CommitmentFollower,
    CommitmentNotice,
)
from gobernar360.platform.commitment_rules import DONE, OPEN, OVERDUE
from gobernar360.platform.listing import every_word
from gobernar360.platform.models import Membership, User
from gobernar360.platform.subjects import SubjectIn
from gobernar360.platform.tenant_crud import create_entity, delete_entity, update_entity

ASSIGNED = "assigned"
OWNER_LEFT = "owner_left"


@dataclass(frozen=True)
class Rights:
    """What one member may do with one commitment."""

    see: bool
    # Say it is done.
    finish: bool
    # Change who owes it, by when, and who is attached.
    reschedule: bool
    # Drop or reopen it.
    manage: bool
    # Change what was agreed and what it is about.
    edit: bool
    # Add progress notes.
    note: bool


def _follows(user_id: uuid.UUID) -> ColumnElement[bool]:
    return (
        select(CommitmentFollower.id)
        .where(
            CommitmentFollower.commitment_id == Commitment.id,
            CommitmentFollower.user_id == user_id,
        )
        .correlate(Commitment)
        .exists()
    )


def _created_informally(user_id: uuid.UUID) -> ColumnElement[bool]:
    return and_(Commitment.source.is_(None), Commitment.created_by == user_id)


def visible(ctx: RequestContext) -> ColumnElement[bool]:
    """The commitments the member may see, as a condition of a query."""
    sources = list(effective_levels(ctx.db, ctx.membership))
    return or_(
        Commitment.owner_id == ctx.user.id,
        _created_informally(ctx.user.id),
        Commitment.source.in_(sources),
        _follows(ctx.user.id),
    )


def rights(ctx: RequestContext, commitment: Commitment) -> Rights:
    return rights_on(ctx, [commitment])[commitment.id]


def rights_on(ctx: RequestContext, commitments: Sequence[Commitment]) -> dict[uuid.UUID, Rights]:
    me = ctx.user.id
    levels = effective_levels(ctx.db, ctx.membership)
    followed = set(
        ctx.db.scalars(
            select(CommitmentFollower.commitment_id).where(
                CommitmentFollower.user_id == me,
                CommitmentFollower.commitment_id.in_([c.id for c in commitments]),
            )
        )
    )

    def of(commitment: Commitment) -> Rights:
        informal = commitment.source is None
        level = AccessLevel.NONE if informal else levels.get(commitment.source, AccessLevel.NONE)
        owes = commitment.owner_id == me
        creator = informal and commitment.created_by == me
        editor = level >= AccessLevel.EDITOR
        return Rights(
            see=owes or creator or level >= AccessLevel.VIEWER or commitment.id in followed,
            finish=owes or editor,
            reschedule=owes or creator or editor,
            manage=creator or editor,
            edit=creator,
            note=owes or creator or editor,
        )

    return {commitment.id: of(commitment) for commitment in commitments}


def load(ctx: RequestContext, commitment_id: uuid.UUID, lock: bool = False) -> Commitment:
    """A commitment the member may see. To anyone else it does not exist."""
    query = select(Commitment).where(Commitment.id == commitment_id, visible(ctx))
    if lock:
        # Two people finishing it at once must not both tell everyone.
        query = query.with_for_update(of=Commitment).execution_options(populate_existing=True)
    commitment = ctx.db.scalars(query).unique().first()
    if commitment is None:
        raise not_found()
    return commitment


def state_conditions(state: str | None, today: date) -> list[ColumnElement[bool]]:
    """Conditions for a state people choose; "pending" is open, overdue or not."""
    if state is None:
        return []
    if state == "pending":
        return [Commitment.state == OPEN]
    if state == OVERDUE:
        return [Commitment.state == OPEN, Commitment.due_date < today]
    if state == OPEN:
        return [Commitment.state == OPEN, Commitment.due_date >= today]
    return [Commitment.state == state]


def query_commitments(today: date, q: str | None = None, state: str | None = None) -> Select[Any]:
    """Commitments matching the filters, those still open first, by due date. It does not
    look at who is asking: add `visible`, or a narrower condition."""
    return (
        select(Commitment)
        .join(User, User.id == Commitment.owner_id)
        .where(
            *every_word(q, Commitment.description, User.full_name), *state_conditions(state, today)
        )
        .order_by(
            case((Commitment.state == OPEN, 0), else_=1),
            Commitment.due_date,
            Commitment.created_at,
            Commitment.id,
        )
    )


def relation(ctx: RequestContext, name: str) -> ColumnElement[bool]:
    """The commitments a member has to do with: those they owe, gave or are attached to."""
    me = ctx.user.id
    if name == "mine":
        return Commitment.owner_id == me
    if name == "given":
        return and_(_created_informally(me), Commitment.owner_id != me)
    return and_(_follows(me), Commitment.owner_id != me)


def followers_of(
    ctx: RequestContext, commitment_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[User]]:
    found: dict[uuid.UUID, list[User]] = {}
    rows = ctx.db.execute(
        select(CommitmentFollower.commitment_id, User)
        .join(User, User.id == CommitmentFollower.user_id)
        .where(CommitmentFollower.commitment_id.in_(list(commitment_ids)))
        .order_by(User.full_name, User.email)
    )
    for commitment_id, user in rows:
        found.setdefault(commitment_id, []).append(user)
    return found


def origins(
    ctx: RequestContext, commitments: Sequence[Commitment]
) -> dict[uuid.UUID, CommitmentOrigin]:
    """Where each was recorded, told by its source, whoever is asking: see `show_origin`."""
    by_source: dict[str, list[uuid.UUID]] = {}
    for commitment in commitments:
        if commitment.source is not None:
            by_source.setdefault(commitment.source, []).append(commitment.id)
    found: dict[uuid.UUID, CommitmentOrigin] = {}
    for source, ids in by_source.items():
        module = registry.get_module(source)
        if module is not None and module.get_commitment_origins is not None:
            found |= module.get_commitment_origins(ctx, ids)
    return found


def sees_source(ctx: RequestContext, commitment: Commitment) -> bool:
    return commitment.source in effective_levels(ctx.db, ctx.membership)


# Changes


def record(
    ctx: RequestContext, commitment: Commitment, note: str = "", changes: dict | None = None
) -> None:
    fields = {"commitment_id": commitment.id, "note": note, "changes": changes or {}}
    create_entity(ctx, CommitmentEntry(**fields), fields)


def _forget_unread(
    ctx: RequestContext, commitment: Commitment, kind: str, user_id: uuid.UUID | None = None
) -> None:
    """Take back what somebody was told and has not read, when it is no longer so."""
    query = delete(CommitmentNotice).where(
        CommitmentNotice.commitment_id == commitment.id,
        CommitmentNotice.kind == kind,
        CommitmentNotice.read_at.is_(None),
    )
    if user_id is not None:
        query = query.where(CommitmentNotice.user_id == user_id)
    ctx.db.execute(query)


def _tell(
    ctx: RequestContext, commitment: Commitment, kind: str, user_ids: Iterable[uuid.UUID]
) -> None:
    """Tell these people, except whoever did it."""
    for user_id in sorted(set(user_ids) - {ctx.user.id}):
        ctx.db.add(
            CommitmentNotice(
                municipality_id=ctx.municipality_id,
                commitment_id=commitment.id,
                user_id=user_id,
                kind=kind,
                created_by=ctx.user.id,
                updated_by=ctx.user.id,
            )
        )
    ctx.db.flush()


def set_followers(
    ctx: RequestContext, commitment: Commitment, user_ids: Iterable[uuid.UUID]
) -> None:
    wanted = set(user_ids)
    current = {
        row.user_id: row
        for row in ctx.db.scalars(
            select(CommitmentFollower).where(CommitmentFollower.commitment_id == commitment.id)
        )
    }
    # Someone already attached may have left the municipality since: they stay.
    directory.resolve_members(ctx, wanted - current.keys(), "follower_ids")
    for user_id in current.keys() - wanted:
        delete_entity(ctx, current[user_id])
    for user_id in sorted(wanted - current.keys()):
        fields = {"commitment_id": commitment.id, "user_id": user_id}
        create_entity(ctx, CommitmentFollower(**fields), fields)


def create(
    ctx: RequestContext,
    today: date,
    *,
    description: str,
    owner_id: uuid.UUID,
    due_date: date,
    subject: SubjectIn | None = None,
    follower_ids: Sequence[uuid.UUID] = (),
    source: str | None = None,
) -> Commitment:
    """Record a commitment and tell whoever owes it. Whoever calls it has checked that the
    member may record one for `source`."""
    owner = directory.resolve_member(ctx, owner_id, "owner_id")
    commitment = Commitment(
        source=source, description=description, owner_id=owner.id, due_date=due_date
    )
    if subject is not None:
        commitment.subject = subjects.resolve(ctx, subject, today)
    create_entity(
        ctx,
        commitment,
        {"description": description, "owner_id": owner.id, "due_date": due_date, "source": source},
    )
    set_followers(ctx, commitment, follower_ids)
    _tell(ctx, commitment, ASSIGNED, [owner.id])
    ctx.db.refresh(commitment)
    return commitment


def reschedule(
    ctx: RequestContext,
    commitment: Commitment,
    *,
    owner_id: uuid.UUID | None = None,
    due_date: date | None = None,
    follower_ids: Sequence[uuid.UUID] | None = None,
    agreed: bool = False,
) -> None:
    """Change who owes it, by when and who is attached, and keep it in its history.

    `agreed` says the new date is part of agreeing on it, e.g. its meeting is still open;
    otherwise the date agreed stays.
    """
    if commitment.state != OPEN:
        raise commitment_finished()
    changes: dict[str, Any] = {}
    recorded: dict[str, list[str]] = {}
    previous = commitment.owner
    if owner_id is not None and owner_id != commitment.owner_id:
        owner = directory.resolve_member(ctx, owner_id, "owner_id")
        changes["owner_id"] = owner.id
        recorded["owner"] = [previous.full_name, owner.full_name]
    if due_date is not None and due_date != commitment.due_date:
        changes["due_date"] = due_date
        if agreed:
            changes["agreed_due_date"] = due_date
        recorded["due_date"] = [commitment.due_date.isoformat(), due_date.isoformat()]
    if follower_ids is not None:
        set_followers(ctx, commitment, follower_ids)
    if not changes:
        return
    update_entity(ctx, commitment, changes)
    record(ctx, commitment, changes=recorded)
    if "owner_id" in changes:
        _forget_unread(ctx, commitment, ASSIGNED, previous.id)
        _forget_unread(ctx, commitment, OWNER_LEFT)
        _tell(ctx, commitment, ASSIGNED, [changes["owner_id"]])


def set_state(
    ctx: RequestContext,
    commitment: Commitment,
    today: date,
    state: str,
    completed_on: date | None = None,
    note: str = "",
) -> None:
    """Say it is done, drop it or open it again, and tell whoever is waiting for it."""
    finished_on = None
    if state == DONE:
        finished_on = completed_on or today
        if finished_on > today:
            raise validation_error("completed_on must not be in the future.")
    before, was_on = commitment.state, commitment.completed_on
    recorded: dict[str, list[str | None]] = {}
    if state != before:
        recorded["state"] = [before, state]
    if finished_on is not None and finished_on != was_on:
        recorded["completed_on"] = [was_on and was_on.isoformat(), finished_on.isoformat()]
    if not recorded and not note:
        # Saying the same again adds nothing to the history.
        return
    update_entity(ctx, commitment, {"state": state, "completed_on": finished_on})
    record(ctx, commitment, note, recorded)
    if state == before:
        return
    if before == DONE:
        _forget_unread(ctx, commitment, DONE)
    if before == OPEN:
        # Nothing left to do for whoever had not yet seen it was theirs.
        _forget_unread(ctx, commitment, ASSIGNED)
        _forget_unread(ctx, commitment, OWNER_LEFT)
    if state == DONE:
        waiting = [user.id for user in followers_of(ctx, [commitment.id]).get(commitment.id, [])]
        if commitment.source is None and commitment.created_by is not None:
            waiting.append(commitment.created_by)
        _tell(ctx, commitment, DONE, waiting)


# Owners who left


def _member_ids(ctx: RequestContext) -> Select[Any]:
    # Memberships are a platform table, without row-level security: filtered here.
    return select(Membership.user_id).where(Membership.municipality_id == ctx.municipality_id)


def left(ctx: RequestContext, user_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    """Those of the people who are no longer members of the municipality."""
    wanted = set(user_ids)
    return wanted - set(ctx.db.scalars(_member_ids(ctx).where(Membership.user_id.in_(wanted))))


@dataclass(frozen=True)
class LeftBehind:
    """Open commitments whose owner is no longer a member."""

    # Those whoever asks may see, soonest due first.
    seen: list[Commitment]
    # How many more there are: who gave them was told, and only they may see them.
    hidden: int


def left_behind(ctx: RequestContext, owner_id: uuid.UUID | None = None) -> LeftBehind:
    """What those who left still owe, or only one of them."""
    conditions = [Commitment.state == OPEN, Commitment.owner_id.not_in(_member_ids(ctx))]
    if owner_id is not None:
        conditions.append(Commitment.owner_id == owner_id)
    total = ctx.db.scalar(select(func.count()).select_from(Commitment).where(*conditions))
    if ctx.membership is None:
        # The platform operator, who sees nothing of what the municipality works on.
        return LeftBehind([], total)
    query = (
        select(Commitment)
        .where(*conditions, visible(ctx))
        .order_by(Commitment.due_date, Commitment.description, Commitment.id)
    )
    seen = list(ctx.db.scalars(query).unique())
    return LeftBehind(seen, total - len(seen))


def tell_owner_left(ctx: RequestContext, user_id: uuid.UUID) -> None:
    """Tell whoever gave something to a person who just left, so they give it to another."""
    given = ctx.db.scalars(
        select(Commitment).where(
            Commitment.state == OPEN,
            Commitment.owner_id == user_id,
            Commitment.source.is_(None),
            # Not whoever left before, nor the person themselves.
            Commitment.created_by.in_(_member_ids(ctx)),
        )
    ).unique()
    for commitment in given:
        _tell(ctx, commitment, OWNER_LEFT, [commitment.created_by])


def forget_owner_left(ctx: RequestContext, user_id: uuid.UUID) -> None:
    """The person is back: take it back from those who have not read it."""
    owed = select(Commitment.id).where(Commitment.owner_id == user_id)
    ctx.db.execute(
        delete(CommitmentNotice).where(
            CommitmentNotice.commitment_id.in_(owed),
            CommitmentNotice.kind == OWNER_LEFT,
            CommitmentNotice.read_at.is_(None),
        )
    )


def require(allowed: bool) -> None:
    if not allowed:
        raise forbidden()


# What people are told


def unread_notices(ctx: RequestContext) -> dict[uuid.UUID, list[tuple[CommitmentNotice, User]]]:
    """What the member was told and has not read, by commitment, newest first."""
    found: dict[uuid.UUID, list[tuple[CommitmentNotice, User]]] = {}
    rows = ctx.db.execute(
        select(CommitmentNotice, User)
        .outerjoin(User, User.id == CommitmentNotice.created_by)
        .where(CommitmentNotice.user_id == ctx.user.id, CommitmentNotice.read_at.is_(None))
        .order_by(CommitmentNotice.created_at.desc(), CommitmentNotice.id)
    )
    for notice, actor in rows:
        found.setdefault(notice.commitment_id, []).append((notice, actor))
    return found


def mark_read(ctx: RequestContext, commitment_id: uuid.UUID | None = None) -> None:
    query = update(CommitmentNotice).where(
        CommitmentNotice.user_id == ctx.user.id, CommitmentNotice.read_at.is_(None)
    )
    if commitment_id is not None:
        query = query.where(CommitmentNotice.commitment_id == commitment_id)
    ctx.db.execute(query.values(read_at=datetime.now(UTC)))


def notification_rows(ctx: RequestContext, today: date) -> list[Commitment]:
    """What a member is asked to keep an eye on: the open ones they owe, gave or are attached
    to, and those delivered that they have not read about."""
    me = ctx.user.id
    told_done = (
        select(CommitmentNotice.id)
        .where(
            CommitmentNotice.commitment_id == Commitment.id,
            CommitmentNotice.user_id == me,
            CommitmentNotice.kind == DONE,
            CommitmentNotice.read_at.is_(None),
        )
        .correlate(Commitment)
        .exists()
    )
    concerned = or_(Commitment.owner_id == me, _created_informally(me), _follows(me))
    query = query_commitments(today).where(concerned, or_(Commitment.state == OPEN, told_done))
    return list(ctx.db.scalars(query).unique())


# The reverse view


def about(
    ctx: RequestContext, dashboard_key: str, kind: str, refs: Iterable[str], today: date
) -> list[Commitment]:
    """Open commitments about some subjects that the member may see, soonest due first.
    They must be able to see the subjects too."""
    subjects.require_visible(ctx, dashboard_key, kind)
    known = [ref for ref in (subjects.normal_ref(kind, ref) for ref in refs) if ref is not None]
    query = select(Commitment).where(
        Commitment.state == OPEN,
        Commitment.subject_dashboard == dashboard_key,
        Commitment.subject_kind == kind,
        Commitment.subject_ref.in_(known),
        visible(ctx),
    )
    rows = ctx.db.scalars(query).unique()
    return sorted(rows, key=lambda c: (c.due_date, c.description, str(c.id)))
