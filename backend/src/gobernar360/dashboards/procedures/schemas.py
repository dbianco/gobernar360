"""Request and response shapes of the procedures dashboard."""

import uuid
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

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
