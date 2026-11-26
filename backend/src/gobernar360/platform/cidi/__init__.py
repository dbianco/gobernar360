"""CiDi, the provincial account of the residents of Córdoba: reaching it, or not.

`GOBERNAR360_CIDI_MODE` decides for the whole installation: `off` (nothing is sent through
it), `fake` (a file in its place) or `live`, which waits for the Province's technical
specification (docs/cidi/questions-for-province.md).
"""

from collections.abc import Callable
from pathlib import Path

from gobernar360.core.config import get_settings
from gobernar360.platform.cidi.connection import Connection
from gobernar360.platform.cidi.fake import FileFakeCidi
from gobernar360.platform.cidi.ports import CommunicationsPort

OFF, FAKE, LIVE = "off", "fake", "live"

# Builds the real adapter from one municipality's connection. There is none until phase B
# of task 19.
live_adapter: Callable[[Connection], CommunicationsPort] | None = None


class CidiNotConfigured(Exception):
    """The installation asks for the real CiDi, which cannot be reached yet."""

    def __init__(self) -> None:
        super().__init__(
            "GOBERNAR360_CIDI_MODE is live, and there is no connection to the real CiDi yet: it "
            "waits for the Province's technical specification. See "
            "docs/cidi/questions-for-province.md."
        )


def fake_inbox() -> FileFakeCidi:
    return FileFakeCidi(Path(get_settings().cidi_fake_inbox))


def get_port(connection: Callable[[], Connection]) -> CommunicationsPort | None:
    """What messages go out through; None when CiDi is off.

    `connection` gives the municipality's own, and is only asked for by the real adapter:
    its secrets are not decrypted for anything else.
    """
    if not is_on():
        return None
    if get_settings().cidi_mode == FAKE:
        return fake_inbox()
    return live_adapter(connection())


def is_on() -> bool:
    """Whether the installation sends anything through CiDi. Raises `CidiNotConfigured` when
    it asks for the real one and there is no way to reach it."""
    mode = get_settings().cidi_mode
    if mode == LIVE and live_adapter is None:
        raise CidiNotConfigured()
    return mode != OFF


def is_available() -> bool:
    """Whether anything can be sent through CiDi from this installation."""
    try:
        return is_on()
    except CidiNotConfigured:
        return False
