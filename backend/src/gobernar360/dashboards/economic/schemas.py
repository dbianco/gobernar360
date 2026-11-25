"""Request and response shapes of the economic dashboard."""

import datetime as dt
import re
import uuid
from typing import Annotated, Any, ClassVar, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from gobernar360.platform.api_types import Name, OrmModel, PatchModel, Year
from gobernar360.platform.people import PersonIn, PersonOut, PersonPatch

Audience = Literal["actors", "people", "both"]
EmploymentStatus = Literal[
    "unknown", "employed", "self_employed", "unemployed", "student", "retired", "other"
]
Role = Literal["owner", "contact", "employee"]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
EmployeeCount = Annotated[int, Field(ge=0, le=1_000_000)]


# Runs once, while the schemas are defined, where mutation testing cannot reach it (hence
# the pragma); the request tests check what it enforces.
def _text(max_length: int) -> Any:  # pragma: no mutate block
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=max_length)]


def _strip_cuit(value: Any) -> Any:
    """People type tax ids as 30-71234567-8."""
    return value.replace("-", "").replace(" ", "") if isinstance(value, str) else value


def _check_cuit(value: str) -> str:
    if value and not re.fullmatch(r"\d{11}", value):
        raise ValueError("must have 11 digits")
    return value


Cuit = Annotated[str, BeforeValidator(_strip_cuit), AfterValidator(_check_cuit)]


class NamedRef(OrmModel):
    id: uuid.UUID
    name: str


class NameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class SubcategoryIn(BaseModel):
    category_id: uuid.UUID
    name: Name


class SubcategoryOut(OrmModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str


class ToolIn(BaseModel):
    category_id: uuid.UUID
    subcategory_id: uuid.UUID | None = None
    name: Name
    description: LongText = ""
    audience: Audience = "both"


class ToolPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")
    nullable: ClassVar[frozenset[str]] = frozenset({"subcategory_id"})

    category_id: uuid.UUID | None = None
    subcategory_id: uuid.UUID | None = None
    name: Name | None = None
    description: LongText | None = None
    audience: Audience | None = None


class ToolOut(OrmModel):
    id: uuid.UUID
    name: str
    description: str
    audience: str
    category: NamedRef
    subcategory: NamedRef | None


class ActorIn(BaseModel):
    name: Name
    actor_type_id: uuid.UUID | None = None
    sector_id: uuid.UUID | None = None
    cuit: Cuit = ""
    address: _text(200) = ""
    phone: _text(50) = ""
    email: _text(200) = ""
    employee_count: EmployeeCount | None = None
    notes: LongText = ""


class ActorPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")
    nullable: ClassVar[frozenset[str]] = frozenset({"actor_type_id", "sector_id", "employee_count"})

    name: Name | None = None
    actor_type_id: uuid.UUID | None = None
    sector_id: uuid.UUID | None = None
    cuit: Cuit | None = None
    address: _text(200) | None = None
    phone: _text(50) | None = None
    email: _text(200) | None = None
    employee_count: EmployeeCount | None = None
    notes: LongText | None = None


class ActorOut(OrmModel):
    id: uuid.UUID
    name: str
    actor_type: NamedRef | None
    sector: NamedRef | None
    cuit: str
    address: str
    phone: str
    email: str
    employee_count: int | None
    notes: str
    # Worked out from the actor's location.
    zones: list[NamedRef]


class EconomicPersonIn(BaseModel):
    person: PersonIn
    employment_status: EmploymentStatus = "unknown"
    occupation: _text(200) = ""


class EconomicPersonPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")

    person: PersonPatch | None = None
    employment_status: EmploymentStatus | None = None
    occupation: _text(200) | None = None


class EconomicPersonOut(OrmModel):
    """A person as this dashboard sees them. `id` is the dashboard's own id for the person."""

    id: uuid.UUID
    person: PersonOut
    employment_status: str
    occupation: str


class LookupOut(BaseModel):
    # The registry's person with that document, if any.
    person: PersonOut | None
    # Set when that person is already incorporated into this dashboard.
    registered_id: uuid.UUID | None


class ActorPersonIn(BaseModel):
    person_id: uuid.UUID
    role: Role


class ActorPersonOut(OrmModel):
    id: uuid.UUID
    role: str
    person: EconomicPersonOut


class ActorDetail(ActorOut):
    people: list[ActorPersonOut]


class PersonActorOut(OrmModel):
    id: uuid.UUID
    role: str
    actor: NamedRef


class PersonDetail(EconomicPersonOut):
    actors: list[PersonActorOut]


class PersonRef(OrmModel):
    id: uuid.UUID
    full_name: str


class AssignmentIn(BaseModel):
    tool_id: uuid.UUID
    actor_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    date: dt.date
    note: LongText = ""

    @model_validator(mode="after")
    def has_exactly_one_recipient(self) -> "AssignmentIn":
        if (self.actor_id is None) == (self.person_id is None):
            raise ValueError("exactly one of actor_id and person_id is required")
        return self


class AssignmentPatch(PatchModel):
    """Who received which tool is fixed; a wrong assignment is deleted and loaded again."""

    model_config = ConfigDict(extra="forbid")

    date: dt.date | None = None
    note: LongText | None = None


class AssignmentOut(OrmModel):
    id: uuid.UUID
    date: dt.date
    note: str
    tool: NamedRef
    actor: NamedRef | None
    person: PersonRef | None


class RecipientCount(BaseModel):
    total: int
    # How many of them received at least one tool in the year.
    with_assignments: int


class ToolCount(BaseModel):
    tool: str
    category: str
    count: int


class SummaryOut(BaseModel):
    year: Year
    actors: RecipientCount
    people: RecipientCount
    tools: int
    assignments: int
    actor_tools: list[ToolCount]
    person_tools: list[ToolCount]


class NameCount(BaseModel):
    # None groups the records that have no value for the dimension.
    name: str | None
    count: int


class StatusCount(BaseModel):
    status: str
    count: int


class MonthCount(BaseModel):
    month: int
    count: int


class ReportsOut(BaseModel):
    year: Year
    actors_by_type: list[NameCount]
    actors_by_sector: list[NameCount]
    people_by_employment_status: list[StatusCount]
    assignments_by_category: list[NameCount]
    assignments_by_month: list[MonthCount]
