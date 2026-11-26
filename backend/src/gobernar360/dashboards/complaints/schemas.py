"""Request and response shapes of the complaints dashboard."""

import uuid
from datetime import date, datetime
from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from gobernar360.dashboards.complaints.models import MAX_TARGET_DAYS
from gobernar360.platform.api_types import Name, OrmModel, PatchModel
from gobernar360.platform.people import PersonIn, PersonOut
from gobernar360.platform.resident_notices import MAX_MESSAGE

State = Literal[
    "received", "assigned", "in_progress", "waiting", "resolved", "closed", "rejected", "reopened"
]
ClockStatus = Literal["on_time", "at_risk", "overdue"]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
MessageToResident = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_MESSAGE)]
TargetDays = Annotated[int, Field(ge=1, le=MAX_TARGET_DAYS)]
Weekday = Annotated[int, Field(ge=1, le=7)]


class NamedRef(OrmModel):
    id: uuid.UUID
    name: str


class NameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class TypeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    area_id: uuid.UUID
    target_days: TargetDays
    is_active: bool = True


class TypePatch(PatchModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    area_id: uuid.UUID | None = None
    target_days: TargetDays | None = None
    is_active: bool | None = None


class TypeOut(OrmModel):
    id: uuid.UUID
    name: str
    area: NamedRef
    target_days: int
    is_active: bool


class HolidayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    name: Name


class HolidayOut(OrmModel):
    id: uuid.UUID
    date: date
    name: str


class WorkingWeekIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekdays: Annotated[list[Weekday], Field(min_length=1, max_length=7)]


class CalendarOut(BaseModel):
    weekdays: list[int]
    holidays: list[HolidayOut]


class ComplaintIn(BaseModel):
    """A new complaint. The resident is someone of the registry, someone new, or nobody."""

    model_config = ConfigDict(extra="forbid")

    type_id: uuid.UUID
    zone_id: uuid.UUID
    address: Address
    description: Description = ""
    # A person found in the registry by document number.
    person_id: uuid.UUID | None = None
    # Someone not in the registry yet, added to it with the complaint.
    new_person: PersonIn | None = None

    @model_validator(mode="after")
    def one_resident_at_most(self) -> Self:
        if self.person_id is not None and self.new_person is not None:
            raise ValueError("send person_id or new_person, not both")
        return self


class ComplaintPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")
    nullable: ClassVar[frozenset[str]] = frozenset()

    type_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    address: Address | None = None
    description: Description | None = None


class TransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_state: State
    # For the timeline, which only members see.
    note: Note = ""
    # The only free text that reaches the resident, when the move is one they are told about.
    message_to_resident: MessageToResident = ""


class AssignmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area_id: uuid.UUID
    note: Note = ""


class CommentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ClockOut(BaseModel):
    target_days: int
    used_days: int
    left_days: int
    deadline: date
    status: ClockStatus | None
    paused: bool
    resolved_on: date | None


class PersonRef(OrmModel):
    id: uuid.UUID
    full_name: str


class ComplaintOut(BaseModel):
    id: uuid.UUID
    number: int
    received_at: datetime
    type: NamedRef
    area: NamedRef
    zone: NamedRef
    address: str
    state: State
    person: PersonRef | None
    clock: ClockOut


class UserRef(OrmModel):
    id: uuid.UUID
    full_name: str


class EventOut(OrmModel):
    id: uuid.UUID
    kind: str
    from_state: str | None
    to_state: str | None
    from_area: NamedRef | None
    to_area: NamedRef | None
    from_type: NamedRef | None
    to_type: NamedRef | None
    note: str
    at: datetime
    user: UserRef | None


class ResidentOut(OrmModel):
    """Who made the complaint and how to reach them: what following the case needs, not
    everything the registry holds about the person."""

    id: uuid.UUID
    full_name: str
    dni: str | None
    phone: str


class NoticeOut(OrmModel):
    """That the resident was told something, and how that went. Never what it said."""

    id: uuid.UUID
    kind: str
    channel: str
    state: str
    created_at: datetime
    handed_over_at: datetime | None


class ComplaintDetail(ComplaintOut):
    description: str
    person: ResidentOut | None
    # States this complaint may move to next.
    moves: list[State]
    timeline: list[EventOut]
    # Null for viewers.
    notices: list[NoticeOut] | None


class LookupOut(BaseModel):
    # The registry's person with that document, if any.
    person: PersonOut | None
    # Same shape as the other dashboards' lookup; complaints never "incorporate" people.
    registered_id: None = None


class QueueOut(BaseModel):
    area: NamedRef
    open: int
    at_risk: int
    overdue: int
    paused: int


class Period(BaseModel):
    date_from: date = Field(serialization_alias="from")
    date_to: date = Field(serialization_alias="to")


class StateCount(BaseModel):
    state: State
    count: int


class StatusCount(BaseModel):
    status: ClockStatus
    count: int


class AgeCount(BaseModel):
    # Calendar days since reception: [min_days, max_days], max None for the last bucket.
    min_days: int
    max_days: int | None
    count: int


class Backlog(BaseModel):
    """The backlog as it stands today, whatever the period."""

    open: int
    overdue: int
    at_risk: int
    paused: int
    by_state: list[StateCount]
    by_status: list[StatusCount]
    ageing: list[AgeCount]


class MonthFlow(BaseModel):
    month: str
    received: int
    resolved: int


class Resolution(BaseModel):
    """How the complaints received in the period were solved."""

    received: int
    resolved: int
    on_time: int
    on_time_ratio: float | None
    median_days: float | None
    p90_days: float | None


class GroupResolution(Resolution):
    id: uuid.UUID
    name: str


class RepeatedGroup(BaseModel):
    type: str
    address: str
    zone: str
    count: int
    first_received: date
    last_received: date
    numbers: list[int]


class NameCount(BaseModel):
    name: str
    count: int


class SummaryOut(BaseModel):
    period: Period
    repeat_days: int
    backlog: Backlog
    totals: Resolution
    monthly: list[MonthFlow]
    by_type: list[GroupResolution]
    by_area: list[GroupResolution]
    repeated: list[RepeatedGroup]
    top_zones: list[NameCount]
    top_types: list[NameCount]
