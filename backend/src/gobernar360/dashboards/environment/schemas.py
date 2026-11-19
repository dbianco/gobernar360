"""Request and response shapes of the environment dashboard."""

import uuid
from decimal import Decimal
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from gobernar360.platform.api_types import Name, OrmModel, PatchModel

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
