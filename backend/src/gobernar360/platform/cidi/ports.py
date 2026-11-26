"""What the platform needs from CiDi, in its own words.

CiDi's technical interface is not public (docs/cidi/README.md): nothing here is the
Province's. An adapter maps this to whatever its documents say, when they arrive; a fake
implements exactly this for tests and local use.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Communication:
    # 11 digits, no separators: the CiDi user name.
    recipient_cuil: str
    # Short; plain text.
    subject: str
    # Plain text.
    body: str
    # Ours, so that a retry never sends twice.
    reference: str


@dataclass(frozen=True)
class Receipt:
    # Whatever CiDi returns to find the message again.
    external_id: str
    accepted_at: datetime


class CidiError(Exception): ...


class RecipientUnknown(CidiError):
    """There is no CiDi account for that CUIL."""


class Unavailable(CidiError):
    """Try again later."""


class CommunicationsPort(Protocol):
    def send(self, communication: Communication) -> Receipt: ...
