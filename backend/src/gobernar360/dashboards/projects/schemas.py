"""Request and response shapes of the projects dashboard."""

import uuid
from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Year = Annotated[int, Field(ge=1900, le=2200)]
Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=16, decimal_places=2),
    PlainSerializer(lambda value: f"{value:.2f}", return_type=str),
]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


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
