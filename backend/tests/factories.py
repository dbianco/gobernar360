"""Builders for test data. They write through the owner connection, which bypasses RLS."""

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.core.db import get_admin_engine
from gobernar360.core.security import hash_password, normalize_email
from gobernar360.platform.models import (
    DashboardGrant,
    EmailOutbox,
    Membership,
    Municipality,
    MunicipalityDashboard,
    MunicipalitySettings,
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
    password: str | None = DEFAULT_PASSWORD,
    operator: bool = False,
    active: bool = True,
) -> User:
    """An account; `password=None` is one that was invited and never chose a password."""
    user = User(
        email=normalize_email(email),
        full_name=email.split("@")[0].title(),
        password_hash=None if password is None else hash_password(password),
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


def configure(
    municipality: Municipality, notification_emails: list[str] | None = None, sso: bool = False
) -> None:
    """Set what the municipality's administrators would set in Configuración."""
    with admin_session() as session, session.begin():
        session.add(
            MunicipalitySettings(
                municipality_id=municipality.id,
                notification_emails=notification_emails or [],
                sso_enabled=sso,
            )
        )


def login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response


def emails_to(address: str) -> list[EmailOutbox]:
    """Emails queued for an address, oldest first."""
    with admin_session() as session:
        return list(
            session.scalars(
                select(EmailOutbox)
                .where(EmailOutbox.to_address == address)
                .order_by(EmailOutbox.created_at, EmailOutbox.id)
            )
        )


def link_token(email: EmailOutbox) -> str:
    """The token of the set-password link in an email."""
    match = re.search(r"/set-password#([\w-]+)", email.body)
    assert match, email.body
    return match.group(1)


def accept_invitation(client: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> None:
    """Follow the latest link emailed to `email` and choose `password`."""
    token = link_token(emails_to(email)[-1])
    response = client.post("/api/auth/tokens/redeem", json={"token": token, "password": password})
    assert response.status_code == 204, response.text


def current_overview(overview: list[dict]) -> list[dict]:
    """The general overview without the evolution of its indicators: each dashboard's
    indicators as key, value and unit, and its lights."""
    return [
        {
            "dashboard_key": section["dashboard_key"],
            "indicators": [
                {"key": item["key"], "value": item["value"], "unit": item["unit"]}
                for item in section["indicators"]
            ],
            "status": section["status"],
        }
        for section in overview
    ]
