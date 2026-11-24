"""Response and request shapes shared by the platform routers."""

import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from gobernar360.core.security import normalize_email

MIN_PASSWORD_LENGTH = 10


def _valid_email(raw: str) -> str:
    email = normalize_email(raw)
    local, _, domain = email.partition("@")
    if not local or "." not in domain or " " in email:
        raise ValueError("must be a valid email address")
    return email


Email = Annotated[str, Field(max_length=320), AfterValidator(_valid_email)]
Password = Annotated[str, Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)]
FullName = Annotated[str, Field(min_length=1, max_length=200)]
GrantLevel = Literal["viewer", "editor", "admin"]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(OrmModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_platform_operator: bool


class MunicipalityOut(OrmModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: str


class MembershipOut(OrmModel):
    municipality: MunicipalityOut
    is_admin: bool


class DashboardAccessOut(BaseModel):
    key: str
    level: str


class Me(BaseModel):
    user: UserOut
    # Municipalities the user can work in now; suspended ones are listed apart.
    memberships: list[MembershipOut]
    active_municipality_id: uuid.UUID | None
    dashboards: list[DashboardAccessOut]
    suspended_municipalities: list[MunicipalityOut]
