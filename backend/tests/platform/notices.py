"""What the tests of notices to residents share."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from gobernar360.core.config import get_settings
from gobernar360.platform import cidi
from gobernar360.platform.models import MunicipalitySettings, Person
from gobernar360.platform.resident_notice_models import ResidentNotice
from tests.factories import admin_session

CUIL = "20123456786"
OTHER_CUIL = "27111111117"


@pytest.fixture
def fake_cidi(monkeypatch, tmp_path):
    """The installation with the fake CiDi, and its inbox."""
    monkeypatch.setattr(get_settings(), "cidi_mode", "fake")
    monkeypatch.setattr(get_settings(), "cidi_fake_inbox", str(tmp_path / "inbox.jsonl"))
    return cidi.fake_inbox()


@pytest.fixture
def secrets_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(get_settings(), "secrets_key", key)
    return key


def use_channel(municipality, channel: str) -> None:
    """How the municipality tells its residents things, whatever its adhesion."""
    with admin_session() as session, session.begin():
        session.add(
            MunicipalitySettings(municipality_id=municipality.id, resident_notice_channel=channel)
        )


def make_resident(municipality, cuil=None, email="", first="Lucía", last="Fernández") -> Person:
    person = Person(
        municipality_id=municipality.id, first_name=first, last_name=last, cuil=cuil, email=email
    )
    with admin_session() as session, session.begin():
        session.add(person)
    return person


def notices() -> list[ResidentNotice]:
    """Every notice, in the order they were made."""
    with admin_session() as session:
        return list(
            session.scalars(
                select(ResidentNotice).order_by(ResidentNotice.created_at, ResidentNotice.channel)
            )
        )


def outcomes() -> list[tuple[str, str]]:
    return [(notice.channel, notice.state) for notice in notices()]
