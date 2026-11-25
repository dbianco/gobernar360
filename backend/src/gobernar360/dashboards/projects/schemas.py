"""Request and response shapes of the projects dashboard."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

from gobernar360.platform.api_types import Name, OrmModel, PatchModel, Year

Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=16, decimal_places=2),
    PlainSerializer(lambda value: f"{value:.2f}", return_type=str),
]


class NamedRef(OrmModel):
    id: uuid.UUID
    name: str


class TermIn(BaseModel):
    name: Name
    start_year: Year
    end_year: Year

    @model_validator(mode="after")
    def years_are_ordered(self) -> Self:
        if self.end_year < self.start_year:
            raise ValueError("end_year must not be before start_year")
        return self


class TermPatch(BaseModel):
    name: Name | None = None
    start_year: Year | None = None
    end_year: Year | None = None


class TermOut(OrmModel):
    id: uuid.UUID
    name: str
    start_year: int
    end_year: int


class AnnualBudgetIn(BaseModel):
    year: Year
    total_amount: Money


class AnnualBudgetOut(OrmModel):
    year: int
    total_amount: Money


class AxisIn(BaseModel):
    term_id: uuid.UUID
    name: Name


class AxisOut(OrmModel):
    id: uuid.UUID
    term_id: uuid.UUID
    name: str


class ObjectiveIn(BaseModel):
    axis_id: uuid.UUID
    name: Name


class ObjectiveOut(OrmModel):
    id: uuid.UUID
    axis_id: uuid.UUID
    name: str


class NamePatch(BaseModel):
    name: Name


class NameIn(BaseModel):
    name: Name


class OwnerIn(BaseModel):
    full_name: Name


class OwnerOut(OrmModel):
    id: uuid.UUID
    full_name: str


Priority = Literal["A+", "A", "B", "C"]
StoredStatus = Literal["not_started", "in_progress", "finished"]
EffectiveStatus = Literal["not_started", "in_progress", "delayed", "finished"]
SdgNumber = Annotated[int, Field(ge=1, le=17)]
Progress = Annotated[int, Field(ge=0, le=100)]
Measure = Annotated[Decimal, Field(max_digits=18, decimal_places=4)]


class ProjectIn(BaseModel):
    term_id: uuid.UUID
    name: Name
    description: Annotated[str, Field(max_length=5000)] = ""
    axis_id: uuid.UUID
    objective_id: uuid.UUID | None = None
    department_id: uuid.UUID
    owner_id: uuid.UUID | None = None
    program_id: uuid.UUID | None = None
    priority: Priority
    year: Year
    start_date: date | None = None
    end_date: date | None = None
    planned_budget: Money = Decimal("0")
    executed_budget: Money = Decimal("0")
    status: StoredStatus = "not_started"
    manual_progress: Progress | None = None
    sdgs: list[SdgNumber] = []


class ProjectPatch(PatchModel):
    """Only the fields present in the request are changed; the term cannot be changed."""

    nullable = frozenset(
        {"objective_id", "owner_id", "program_id", "start_date", "end_date", "manual_progress"}
    )

    name: Name | None = None
    description: Annotated[str, Field(max_length=5000)] | None = None
    axis_id: uuid.UUID | None = None
    objective_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    program_id: uuid.UUID | None = None
    priority: Priority | None = None
    year: Year | None = None
    start_date: date | None = None
    end_date: date | None = None
    planned_budget: Money | None = None
    executed_budget: Money | None = None
    status: StoredStatus | None = None
    manual_progress: Progress | None = None
    sdgs: list[SdgNumber] | None = None


class MilestoneIn(BaseModel):
    name: Name
    due_date: date
    completed_on: date | None = None


class MilestonePatch(PatchModel):
    nullable = frozenset({"completed_on"})

    name: Name | None = None
    due_date: date | None = None
    completed_on: date | None = None


class MilestoneOut(BaseModel):
    id: uuid.UUID
    name: str
    due_date: date
    completed_on: date | None
    in_alert: bool


class OwnerRef(OrmModel):
    id: uuid.UUID
    full_name: str


class ProjectOut(BaseModel):
    id: uuid.UUID
    term_id: uuid.UUID
    name: str
    description: str
    axis: NamedRef
    objective: NamedRef | None
    department: NamedRef
    owner: OwnerRef | None
    program: NamedRef | None
    priority: str
    year: int
    start_date: date | None
    end_date: date | None
    planned_budget: Money
    executed_budget: Money
    status: StoredStatus
    effective_status: EffectiveStatus
    progress: int
    manual_progress: int | None
    sdgs: list[int]
    milestones: list[MilestoneOut]
    # Worked out from the project's location.
    zones: list[NamedRef]


class IndicatorIn(BaseModel):
    objective_id: uuid.UUID
    name: Name
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] = ""
    baseline: Measure | None = None
    target: Measure | None = None
    current_value: Measure | None = None


class IndicatorPatch(PatchModel):
    nullable = frozenset({"baseline", "target", "current_value"})

    objective_id: uuid.UUID | None = None
    name: Name | None = None
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] | None = None
    baseline: Measure | None = None
    target: Measure | None = None
    current_value: Measure | None = None


class IndicatorOut(BaseModel):
    id: uuid.UUID
    name: str
    unit: str
    baseline: float | None
    target: float | None
    current_value: float | None
    objective: NamedRef
    axis: NamedRef
