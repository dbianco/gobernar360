"""Request and response shapes of the social dashboard."""

import datetime as dt
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from gobernar360.platform.api_types import Name, OrmModel, PatchModel, Year
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
Quantity = Annotated[int, Field(ge=1, le=1_000_000)]


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


class BenefitRef(OrmModel):
    id: uuid.UUID
    name: str
    category: NamedRef


class DeliveryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benefit_id: uuid.UUID
    person_id: uuid.UUID
    date: dt.date
    quantity: Quantity = 1
    note: LongText = ""


class DeliveryPatch(PatchModel):
    """Who received what is fixed; a wrong delivery is deleted and loaded again."""

    model_config = ConfigDict(extra="forbid")

    date: dt.date | None = None
    quantity: Quantity | None = None
    note: LongText | None = None


class DeliveryOut(OrmModel):
    id: uuid.UUID
    date: dt.date
    quantity: int
    note: str
    benefit: BenefitRef
    person: PersonRef


class InterventionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_type_id: uuid.UUID
    person_id: uuid.UUID
    date: dt.date
    description: LongText = ""
    performed_by: _text(200) = ""


class InterventionPatch(PatchModel):
    """The person and the type are fixed; a wrong intervention is deleted and loaded again."""

    model_config = ConfigDict(extra="forbid")

    date: dt.date | None = None
    description: LongText | None = None
    performed_by: _text(200) | None = None


class InterventionOut(BaseModel):
    """Built by `interventions_router.present`, never straight from the row,
    so the reserved text cannot reach a reader by accident."""

    id: uuid.UUID
    date: dt.date
    intervention_type: NamedRef
    person: PersonRef
    performed_by: str
    # None when the reader may not see it.
    description: str | None


class BenefitCount(BaseModel):
    benefit: str
    category: str
    deliveries: int
    # Sum of the quantities delivered.
    units: int


class NameCount(BaseModel):
    # None groups the records that have no value for the dimension.
    name: str | None
    count: int


class MonthCount(BaseModel):
    month: int
    count: int


class SummaryOut(BaseModel):
    year: Year
    people: int
    households: int
    # People who received at least one benefit in the year.
    people_with_deliveries: int
    deliveries: int
    units: int
    interventions: int
    people_with_interventions: int
    benefits: list[BenefitCount]
    intervention_types: list[NameCount]


class ReportsOut(BaseModel):
    year: Year
    deliveries_by_category: list[NameCount]
    deliveries_by_month: list[MonthCount]
    interventions_by_type: list[NameCount]
    interventions_by_month: list[MonthCount]
    people_by_neighborhood: list[NameCount]
    deliveries_by_neighborhood: list[NameCount]
