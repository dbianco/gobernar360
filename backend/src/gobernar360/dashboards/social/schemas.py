"""Request and response shapes of the social dashboard."""

import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from gobernar360.platform.api_types import Name, OrmModel, PatchModel
from gobernar360.platform.people import PersonIn, PersonOut, PersonPatch

Relationship = Literal[
    "head",
    "partner",
    "child",
    "parent",
    "sibling",
    "grandparent",
    "grandchild",
    "other_relative",
    "non_relative",
]

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


class SocialPersonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person: PersonIn


class SocialPersonPatch(PatchModel):
    """Household membership is changed through the household, not here."""

    model_config = ConfigDict(extra="forbid")

    person: PersonPatch | None = None


class SocialPersonOut(OrmModel):
    """A person as this dashboard sees them. `id` is the dashboard's own id for the person."""

    id: uuid.UUID
    person: PersonOut
    household: NamedRef | None
    relationship: str | None


class LookupOut(BaseModel):
    # The registry's person with that document, if any.
    person: PersonOut | None
    # Set when that person is already incorporated into this dashboard.
    registered_id: uuid.UUID | None


class PersonRef(OrmModel):
    id: uuid.UUID
    full_name: str


class HouseholdIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    address: _text(200) = ""
    neighborhood: _text(100) = ""


class HouseholdPatch(PatchModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    address: _text(200) | None = None
    neighborhood: _text(100) | None = None


class HouseholdOut(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    neighborhood: str
    member_count: int
    head: PersonRef | None


class MemberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship: Relationship


class MemberOut(OrmModel):
    # The dashboard's id for the person.
    id: uuid.UUID
    full_name: str
    dni: str | None
    relationship: str


class HouseholdDetail(HouseholdOut):
    members: list[MemberOut]
