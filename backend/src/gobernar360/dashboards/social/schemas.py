"""Request and response shapes of the social dashboard."""

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints

from gobernar360.platform.api_types import Name, OrmModel, PatchModel

LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


def _text(max_length: int) -> Any:
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=max_length)]


class NamedRef(OrmModel):
    id: uuid.UUID
    name: str


class NameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class BenefitIn(BaseModel):
    category_id: uuid.UUID
    name: Name
    description: LongText = ""


class BenefitPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID | None = None
    name: Name | None = None
    description: LongText | None = None


class BenefitOut(OrmModel):
    id: uuid.UUID
    name: str
    description: str
    category: NamedRef
