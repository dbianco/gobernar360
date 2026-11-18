"""Builders for test data. They write through the owner connection, which bypasses RLS."""

from sqlalchemy.orm import Session

from gobernar360.core.db import get_admin_engine
from gobernar360.platform.models import Municipality


def admin_session() -> Session:
    return Session(get_admin_engine(), expire_on_commit=False)


def make_municipality(name: str = "Noetinger", kind: str = "municipality") -> Municipality:
    municipality = Municipality(name=name, slug=name.lower().replace(" ", "-"), kind=kind)
    with admin_session() as session, session.begin():
        session.add(municipality)
    return municipality
