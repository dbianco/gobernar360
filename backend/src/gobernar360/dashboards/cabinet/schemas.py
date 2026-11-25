"""Request and response shapes of the cabinet dashboard."""

import datetime as dt
import uuid
from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from gobernar360.platform.api_types import Name, PatchModel
from gobernar360.platform.commitment_schemas import EffectiveState, Ids
from gobernar360.platform.directory import UserRef
from gobernar360.platform.subjects import SubjectIn, SubjectOut

ItemSource = Literal["manual", "light", "commitment"]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10_000)]


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
    followers: list[UserRef]
    item_id: uuid.UUID
    # Where it was taken.
    meeting: MeetingRef


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
