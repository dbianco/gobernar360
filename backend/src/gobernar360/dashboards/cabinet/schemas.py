"""Request and response shapes of the cabinet dashboard."""

import datetime as dt
import uuid
from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from gobernar360.platform.api_types import Name, OrmModel, PatchModel
from gobernar360.platform.subjects import SubjectIn, SubjectOut

EffectiveState = Literal["overdue", "open", "done", "dropped"]
StoredState = Literal["open", "done", "dropped"]
ItemSource = Literal["manual", "light", "commitment"]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10_000)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
OptionalNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Ids = Annotated[list[uuid.UUID], Field(max_length=200)]


class UserRef(OrmModel):
    id: uuid.UUID
    full_name: str


class MemberOut(UserRef):
    # Whoever has no access to this dashboard can owe a commitment but not follow it here.
    has_access: bool


class MeetingRef(BaseModel):
    id: uuid.UUID
    date: dt.date
    closed: bool


class CommitmentOut(BaseModel):
    id: uuid.UUID
    description: str
    owner: UserRef
    due_date: dt.date
    state: EffectiveState
    completed_on: dt.date | None
    times_postponed: int
    subject: SubjectOut | None
    item_id: uuid.UUID
    # Where it was taken.
    meeting: MeetingRef


class HistoryEntry(BaseModel):
    id: uuid.UUID
    at: dt.datetime
    # None when the author's account no longer exists.
    author: str | None
    note: str
    # field -> [before, after]
    changes: dict[str, tuple[str | None, str | None]]


class CommitmentDetail(CommitmentOut):
    # Newest first.
    history: list[HistoryEntry]


class CommitmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Description
    owner_id: uuid.UUID
    due_date: dt.date
    subject: SubjectIn | None = None


class CommitmentPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")
    nullable: ClassVar[frozenset[str]] = frozenset({"subject"})

    description: Description | None = None
    owner_id: uuid.UUID | None = None
    due_date: dt.date | None = None
    subject: SubjectIn | None = None


class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Note


class StateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: StoredState
    # When it was delivered; today if not given. Only for "done".
    completed_on: dt.date | None = None
    note: OptionalNote = ""

    @model_validator(mode="after")
    def only_done_has_a_date(self) -> Self:
        if self.completed_on is not None and self.state != "done":
            raise ValueError("only a done commitment has a completion date")
        return self


class ProposalOut(BaseModel):
    """Something proposed for a meeting's agenda."""

    # How to accept it when creating the meeting.
    key: str
    source: ItemSource
    title: str
    subject: SubjectOut | None
    commitment: CommitmentOut | None
    # Left undiscussed in the previous meeting.
    carried: bool


class AgendaProposalOut(BaseModel):
    proposals: list[ProposalOut]
    # Open commitments the new meeting will carry over.
    to_carry_over: int
    # Dashboards the member has no access to, whose lights were not looked at.
    dashboards_not_considered: int
    # No meeting may be dated before it.
    previous_meeting_date: dt.date | None


class AgendaEntryIn(BaseModel):
    """An accepted proposal (`key`) or an item of one's own (`title`)."""

    model_config = ConfigDict(extra="forbid")

    key: Annotated[str, StringConstraints(max_length=100)] | None = None
    title: Name | None = None

    @model_validator(mode="after")
    def one_or_the_other(self) -> Self:
        if (self.key is None) == (self.title is None):
            raise ValueError("give either key or title")
        return self


class MeetingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: dt.date
    attendee_ids: Ids = []
    guests: LongText = ""
    # In the order it will be discussed.
    agenda: Annotated[list[AgendaEntryIn], Field(max_length=200)] = []


class MeetingPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")

    date: dt.date | None = None
    attendee_ids: Ids | None = None
    guests: LongText | None = None
    notes: LongText | None = None


class MeetingOut(MeetingRef):
    closed_at: dt.datetime | None
    items: int
    commitments: int


class ItemOut(BaseModel):
    id: uuid.UUID
    source: ItemSource
    title: str
    notes: str
    discussed: bool
    carried: bool
    subject: SubjectOut | None
    # The commitment the item follows up.
    topic: CommitmentOut | None
    # Those that came out of the item.
    commitments: list[CommitmentOut]


class MeetingDetail(MeetingRef):
    closed_at: dt.datetime | None
    attendees: list[UserRef]
    guests: str
    notes: str
    items: list[ItemOut]
    # Commitments of earlier meetings that were still open when this one was prepared.
    carried_over: list[CommitmentOut]


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Name
    subject: SubjectIn | None = None


class ItemPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")
    nullable: ClassVar[frozenset[str]] = frozenset({"subject"})

    # Title and subject can be changed only in items typed by a person.
    title: Name | None = None
    subject: SubjectIn | None = None
    notes: LongText | None = None
    discussed: bool | None = None


class OrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_ids: Ids
