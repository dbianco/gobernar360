"""Response and request shapes shared by the platform routers."""

import uuid

from pydantic import BaseModel, ConfigDict


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
    memberships: list[MembershipOut]
    active_municipality_id: uuid.UUID | None
    dashboards: list[DashboardAccessOut]
