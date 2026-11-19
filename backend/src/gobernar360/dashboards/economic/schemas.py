"""Request and response shapes of the economic dashboard."""

import uuid
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from gobernar360.platform.api_types import Name, OrmModel, PatchModel

Audience = Literal["actors", "people", "both"]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


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
