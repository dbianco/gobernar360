"""Reaching CiDi or not, and the fake that stands for it."""

import pytest
from typer.testing import CliRunner

from gobernar360 import cli
from gobernar360.core.config import Settings, get_settings
from gobernar360.platform import cidi
from gobernar360.platform.cidi import CidiNotConfigured
from gobernar360.platform.cidi.fake import FakeCidi, FileFakeCidi
from gobernar360.platform.cidi.ports import (
    CidiError,
    Communication,
    RecipientUnknown,
    Unavailable,
)
from tests.factories import REPOSITORY
from tests.platform.notices import CUIL, OTHER_CUIL, fake_cidi  # noqa: F401


def _message(reference="r-1", cuil=CUIL, subject="Título", body="Línea 1\n\nLínea 2"):
    return Communication(recipient_cuil=cuil, subject=subject, body=body, reference=reference)


def _never():
    raise AssertionError("The connection was read.")


# The fake


def test_the_fake_keeps_what_it_is_sent_and_gives_a_receipt():
    fake = FakeCidi()

    receipt = fake.send(_message())

    assert fake.sent == [_message()]
    assert receipt.external_id == "fake-r-1"
    assert receipt.accepted_at.tzinfo is not None


def test_the_fake_does_not_keep_a_reference_twice():
    fake = FakeCidi()

    receipts = [fake.send(_message()), fake.send(_message()), fake.send(_message("r-2"))]

    assert [message.reference for message in fake.sent] == ["r-1", "r-2"]
    assert receipts[0].external_id == receipts[1].external_id


def test_the_fake_may_not_know_somebody_or_be_down():
    fake = FakeCidi(unknown={CUIL})
    with pytest.raises(RecipientUnknown):
        fake.send(_message())
    assert fake.send(_message(cuil=OTHER_CUIL)).external_id == "fake-r-1"
    with pytest.raises(Unavailable):
        FakeCidi(unknown={CUIL}, unavailable=True).send(_message())
    assert issubclass(RecipientUnknown, CidiError) and issubclass(Unavailable, CidiError)


def test_the_fake_in_a_file_outlives_the_process(tmp_path):
    path = tmp_path / "inbox.jsonl"
    assert FileFakeCidi(path).messages() == []

    FileFakeCidi(path).send(_message())
    FileFakeCidi(path).send(_message())
    FileFakeCidi(path).send(_message("r-2", OTHER_CUIL))

    assert FileFakeCidi(path).messages() == [
        {
            "recipient_cuil": CUIL,
            "subject": "Título",
            "body": "Línea 1\n\nLínea 2",
            "reference": "r-1",
        },
        {
            "recipient_cuil": OTHER_CUIL,
            "subject": "Título",
            "body": "Línea 1\n\nLínea 2",
            "reference": "r-2",
        },
    ]
    assert "Título" in path.read_text(encoding="utf-8")


# The mode


def test_cidi_is_off_unless_told_otherwise():
    assert Settings().cidi_mode == "off"
    assert Settings().cidi_fake_inbox == "./cidi-fake-inbox.jsonl"
    assert cidi.get_port(_never) is None
    assert (cidi.is_on(), cidi.is_available()) == (False, False)


def test_the_fake_mode_writes_to_its_file_and_needs_no_connection(fake_cidi):  # noqa: F811
    port = cidi.get_port(_never)

    assert isinstance(port, FileFakeCidi) and port.path == fake_cidi.path
    assert (cidi.is_on(), cidi.is_available()) == (True, True)


def test_the_live_mode_waits_for_the_province(monkeypatch):
    monkeypatch.setattr(get_settings(), "cidi_mode", "live")

    for attempt in (lambda: cidi.get_port(_never), cidi.is_on):
        with pytest.raises(CidiNotConfigured) as raised:
            attempt()
        assert str(raised.value) == (
            "GOBERNAR360_CIDI_MODE is live, and there is no connection to the real CiDi yet: "
            "it waits for the Province's technical specification. See "
            "docs/cidi/questions-for-province.md."
        )
    assert cidi.is_available() is False
    # The document it points to.
    assert (REPOSITORY / "docs/cidi/questions-for-province.md").exists()


# The inbox


def test_the_inbox_of_the_fake_is_shown(fake_cidi):  # noqa: F811
    empty = CliRunner().invoke(cli.app, ["cidi-fake-inbox"])
    fake_cidi.send(_message())
    full = CliRunner().invoke(cli.app, ["cidi-fake-inbox"])

    assert empty.output == f"There is nothing in {fake_cidi.path}.\n"
    assert full.output == f"To {CUIL}: Título\nLínea 1\n\nLínea 2\n"
