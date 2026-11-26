"""A CiDi of our own, for tests and for trying the platform without the real one."""

import json
from collections.abc import Collection
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gobernar360.platform.cidi.ports import (
    Communication,
    Receipt,
    RecipientUnknown,
    Unavailable,
)


class FakeCidi:
    """Keeps what it is sent. A reference it already has is not kept twice."""

    def __init__(self, unknown: Collection[str] = (), unavailable: bool = False) -> None:
        self.unknown = set(unknown)
        self.unavailable = unavailable
        self.sent: list[Communication] = []

    def send(self, communication: Communication) -> Receipt:
        if self.unavailable:
            raise Unavailable("The fake CiDi is unavailable.")
        if communication.recipient_cuil in self.unknown:
            raise RecipientUnknown("The fake CiDi has no such account.")
        if communication.reference not in self._references():
            self._keep(communication)
        return Receipt(f"fake-{communication.reference}", datetime.now(UTC))

    def _references(self) -> set[str]:
        return {kept.reference for kept in self.sent}

    def _keep(self, communication: Communication) -> None:
        self.sent.append(communication)


class FileFakeCidi(FakeCidi):
    """Keeps what it is sent in a file, one JSON object per line."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def messages(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line]

    def _references(self) -> set[str]:
        return {message["reference"] for message in self.messages()}

    def _keep(self, communication: Communication) -> None:
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(communication), ensure_ascii=False) + "\n")
