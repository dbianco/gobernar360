"""Request and response shapes of the environment dashboard."""

import uuid
from decimal import Decimal
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from gobernar360.platform.api_types import Name, OrmModel, PatchModel, Year

Category = Literal["energy", "waste", "water", "air", "mobility", "biodiversity", "governance"]
Frequency = Literal["monthly", "annual"]
Direction = Literal["higher_is_better", "lower_is_better"]
Source = Literal["municipal", "external"]
Aggregation = Literal["sum", "average", "last"]
Unit = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
# Matches the NUMERIC(18, 4) columns.
Number = Annotated[Decimal, Field(max_digits=18, decimal_places=4)]


class SubcategoryIn(BaseModel):
    category: Category
    name: Name


class SubcategoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class SubcategoryOut(OrmModel):
    id: uuid.UUID
    category: str
    name: str


class VariableIn(BaseModel):
    subcategory_id: uuid.UUID
    name: Name
    unit: Unit = ""
    frequency: Frequency
    target: Number | None = None
    direction: Direction = "higher_is_better"
    source: Source = "municipal"
    annual_aggregation: Aggregation = "sum"


class VariablePatch(PatchModel):
    """The frequency is fixed at creation: loaded values would stop making sense."""

    model_config = ConfigDict(extra="forbid")
    nullable: ClassVar[frozenset[str]] = frozenset({"target"})

    subcategory_id: uuid.UUID | None = None
    name: Name | None = None
    unit: Unit | None = None
    target: Number | None = None
    direction: Direction | None = None
    source: Source | None = None
    annual_aggregation: Aggregation | None = None


class VariableOut(OrmModel):
    id: uuid.UUID
    name: str
    unit: str
    frequency: str
    target: float | None
    direction: str
    source: str
    annual_aggregation: str
    subcategory: SubcategoryOut


class ValueIn(BaseModel):
    variable_id: uuid.UUID
    year: Year
    # 0 is the whole year (annual variables); 1 to 12 are months.
    period: int = Field(ge=0, le=12)
    # None clears the period.
    value: Number | None


class ValueOut(OrmModel):
    variable_id: uuid.UUID
    year: int
    period: int
    value: float


class VariableSummary(BaseModel):
    variable: VariableOut
    # The year's figure, from the values loaded so far.
    value: float | None
    loaded: int
    expected: int
    achievement: float | None
    target_met: bool | None


class CategorySummary(BaseModel):
    category: str
    loaded: int
    expected: int
    variables: list[VariableSummary]


class SummaryOut(BaseModel):
    year: int
    variable_count: int
    loaded: int
    expected: int
    targets_met: int
    targets_missed: int
    categories: list[CategorySummary]


class MonthPoint(BaseModel):
    period: int
    value: float | None


class YearPoint(BaseModel):
    year: int
    value: float
    loaded: int
    expected: int


class SeriesOut(BaseModel):
    variable: VariableOut
    year: int
    monthly: list[MonthPoint]
    annual: list[YearPoint]
