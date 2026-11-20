"""Request and response shapes of the procedures dashboard."""

import uuid
from decimal import Decimal
from typing import Annotated, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from gobernar360.platform.api_types import Name, OrmModel, PatchModel

SourceLevel = Literal["municipal", "provincial", "national", "other"]
Audience = Literal["people", "organizations", "both"]
Channel = Literal["in_person", "online", "both"]
Format = Literal["paper", "digital"]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


class NamedRef(OrmModel):
    id: uuid.UUID
    name: str


class NameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    level: SourceLevel
    area_id: uuid.UUID | None = None


class SourcePatch(PatchModel):
    model_config = ConfigDict(extra="forbid")
    nullable: ClassVar[frozenset[str]] = frozenset({"area_id"})

    name: Name | None = None
    level: SourceLevel | None = None
    area_id: uuid.UUID | None = None


class SourceOut(OrmModel):
    id: uuid.UUID
    name: str
    level: str
    area: NamedRef | None


class RequirementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    description: LongText = ""
    source_id: uuid.UUID | None = None


class RequirementPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")
    nullable: ClassVar[frozenset[str]] = frozenset({"source_id"})

    name: Name | None = None
    description: LongText | None = None
    source_id: uuid.UUID | None = None


class RequirementRef(OrmModel):
    id: uuid.UUID
    name: str
    source: SourceOut | None


class RequirementOut(RequirementRef):
    description: str
    # Procedures that ask for it, active or not.
    procedure_count: int


Url = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=500, pattern=r"^(https?://\S+)?$")
]
Cost = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
DurationDays = Annotated[int, Field(ge=0, le=3650)]
AnnualVolume = Annotated[int, Field(ge=0, le=100_000_000)]


class ProcedureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    description: LongText = ""
    area_id: uuid.UUID
    audience: Audience = "both"
    channel: Channel = "in_person"
    # Only web addresses: the screen shows it as a link.
    url: Url = ""
    is_free: bool = True
    cost: Cost | None = None
    duration_days: DurationDays | None = None
    annual_volume: AnnualVolume | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def free_procedures_have_no_cost(self) -> Self:
        if self.is_free and self.cost is not None:
            raise ValueError("a free procedure has no cost")
        return self


class ProcedurePatch(PatchModel):
    model_config = ConfigDict(extra="forbid")
    nullable: ClassVar[frozenset[str]] = frozenset({"cost", "duration_days", "annual_volume"})

    name: Name | None = None
    description: LongText | None = None
    area_id: uuid.UUID | None = None
    audience: Audience | None = None
    channel: Channel | None = None
    url: Url | None = None
    is_free: bool | None = None
    cost: Cost | None = None
    duration_days: DurationDays | None = None
    annual_volume: AnnualVolume | None = None
    is_active: bool | None = None


class ProcedureOut(OrmModel):
    id: uuid.UUID
    name: str
    description: str
    area: NamedRef
    audience: str
    channel: str
    url: str
    is_free: bool
    cost: Decimal | None
    duration_days: int | None
    annual_volume: int | None
    is_active: bool
    requirement_count: int


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: uuid.UUID
    mandatory: bool = True
    format: Format = "paper"
    note: LongText = ""


class LinkPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")

    mandatory: bool | None = None
    format: Format | None = None
    note: LongText | None = None


class LinkOut(OrmModel):
    id: uuid.UUID
    requirement: RequirementRef
    mandatory: bool
    format: str
    note: str


class ProcedureDetail(ProcedureOut):
    requirements: list[LinkOut]


class NameCount(BaseModel):
    name: str
    count: int


class ChannelCount(BaseModel):
    channel: str
    count: int


class RequirementCount(BaseModel):
    name: str
    # Name of its source; None when the person brings it themselves.
    source: str | None
    count: int


class SummaryOut(BaseModel):
    """Counts over the procedures currently offered."""

    procedures: int
    # Those that can be done online, fully or as one of two channels.
    online: int
    average_requirements: float | None
    requirements: int
    sources: int
    by_area: list[NameCount]
    by_channel: list[ChannelCount]
    top_requirements: list[RequirementCount]


class Reach(BaseModel):
    """How much asking for a source's data weighs on procedures."""

    requirements: int
    procedures: int
    # Estimated yearly volume of those procedures, each counted once.
    annual_volume: int


class SourceOpportunity(Reach):
    source: SourceOut


class OpportunitiesOut(BaseModel):
    sources: list[SourceOpportunity]
    without_source: Reach
