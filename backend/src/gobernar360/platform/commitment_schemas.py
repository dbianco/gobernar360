"""Request and response shapes of commitments and of what people are told about them."""

import datetime as dt
import uuid
from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from gobernar360.platform.api_types import OrmModel, PatchModel
from gobernar360.platform.directory import UserRef
from gobernar360.platform.subjects import SubjectIn, SubjectOut

EffectiveState = Literal["overdue", "open", "done", "dropped"]
StoredState = Literal["open", "done", "dropped"]
# What to list: one effective state, or every commitment still to be delivered.
StateFilter = EffectiveState | Literal["pending"]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
OptionalNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Ids = Annotated[list[uuid.UUID], Field(max_length=200)]


class RightsOut(OrmModel):
    see: bool
    finish: bool
    reschedule: bool
    manage: bool
    edit: bool
    note: bool


class OriginOut(BaseModel):
    label: str
    path: str


class CommitmentOut(BaseModel):
    id: uuid.UUID
    description: str
    owner: UserRef
    # Who gave an informal one. None when it has a source.
    creator: UserRef | None
    due_date: dt.date
    state: EffectiveState
    completed_on: dt.date | None
    times_postponed: int
    subject: SubjectOut | None
    # The dashboard that recorded it. None for informal ones.
    source: str | None
    # Where it was recorded. None for whoever has no access to the source.
    origin: OriginOut | None
    followers: list[UserRef]
    rights: RightsOut


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
    # Told when it is done.
    follower_ids: Ids = []


class CommitmentPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")
    nullable: ClassVar[frozenset[str]] = frozenset({"subject"})

    description: Description | None = None
    owner_id: uuid.UUID | None = None
    due_date: dt.date | None = None
    subject: SubjectIn | None = None
    follower_ids: Ids | None = None


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


class NewsOut(BaseModel):
    kind: Literal["assigned", "done"]
    # None when the account of whoever did it no longer exists.
    actor: str | None
    at: dt.datetime


class NotificationRow(BaseModel):
    id: uuid.UUID
    description: str
    owner: UserRef
    due_date: dt.date
    state: EffectiveState
    completed_on: dt.date | None
    # Not read yet, newest first.
    news: list[NewsOut]


class NotificationsOut(BaseModel):
    # Open ones the member owes.
    mine: list[NotificationRow]
    # Other people's they gave or are attached to: open, or delivered and not read about.
    others: list[NotificationRow]


class ReadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None: everything.
    commitment_id: uuid.UUID | None = None
