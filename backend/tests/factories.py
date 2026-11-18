"""Builders for test data. They write through the owner connection, which bypasses RLS."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from gobernar360.core.db import get_admin_engine
from gobernar360.core.security import hash_password, normalize_email
from gobernar360.platform.models import (
    DashboardGrant,
    Membership,
    Municipality,
    MunicipalityDashboard,
    User,
)

DEFAULT_PASSWORD = "secret-pass-1"


def admin_session() -> Session:
    return Session(get_admin_engine(), expire_on_commit=False)


def make_municipality(name: str = "Noetinger", kind: str = "municipality") -> Municipality:
    municipality = Municipality(name=name, slug=name.lower().replace(" ", "-"), kind=kind)
    with admin_session() as session, session.begin():
        session.add(municipality)
    return municipality


def make_user(
    email: str = "ana@noetinger.test",
    password: str = DEFAULT_PASSWORD,
    operator: bool = False,
    active: bool = True,
) -> User:
    user = User(
        email=normalize_email(email),
        full_name=email.split("@")[0].title(),
        password_hash=hash_password(password),
        is_platform_operator=operator,
        is_active=active,
    )
    with admin_session() as session, session.begin():
        session.add(user)
    return user


def enable_dashboards(municipality: Municipality, keys: list[str]) -> None:
    with admin_session() as session, session.begin():
        for key in keys:
            session.merge(MunicipalityDashboard(municipality_id=municipality.id, dashboard_key=key))


def make_membership(
    user: User,
    municipality: Municipality,
    admin: bool = False,
    grants: dict[str, str] | None = None,
    enable: list[str] | None = None,
) -> Membership:
    """Add a user to a municipality; granted dashboards are enabled unless `enable` is given."""
    grants = grants or {}
    enable_dashboards(municipality, list(grants) if enable is None else enable)
    membership = Membership(user_id=user.id, municipality_id=municipality.id, is_admin=admin)
    membership.grants = [
        DashboardGrant(dashboard_key=key, level=level) for key, level in grants.items()
    ]
    with admin_session() as session, session.begin():
        session.add(membership)
    return membership


def login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response
