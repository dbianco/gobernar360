"""How a municipality tells its residents things, and its own connection to CiDi.

Each municipality adheres to CiDi itself, so each one has its own connection. It is saved
apart from the rest of Configuración, all at once, by its administrators or the operator.
Secrets are write-only: they are accepted and encrypted, and nothing here gives them back.
"""

from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator

from gobernar360.core import secrets
from gobernar360.core.errors import cidi_not_ready, secrets_key_missing
from gobernar360.platform import cidi, municipality_settings
from gobernar360.platform.access import RequestContext
from gobernar360.platform.audit import apply_audit_fields, record_change
from gobernar360.platform.cidi import connection
from gobernar360.platform.cidi.connection import PLAIN_VALUES
from gobernar360.platform.models import EMAIL_ONLY, MunicipalitySettings
from gobernar360.platform.resident_notice_models import (
    NOT_REQUESTED,
    CidiConnection,
    CidiConnectionValue,
)
from gobernar360.platform.tenant_crud import create_entity, update_entity

Channel = Literal["email", "cidi_then_email", "cidi"]
AdhesionState = Literal["not_requested", "requested", "approved"]
MAX_SECRETS = 20


def _text(max_length: int) -> Any:
    return Annotated[str, StringConstraints(strip_whitespace=True, max_length=max_length)]


SecretName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,49}$")]


class SecretIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Whatever the Province calls it, e.g. api_key.
    name: SecretName
    value: Annotated[SecretStr, Field(min_length=1, max_length=20_000)]

    @field_validator("name")
    @classmethod
    def is_not_plain(cls, name: str) -> str:
        if name in PLAIN_VALUES:
            raise ValueError("is not a secret")
        return name


class NoticeSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resident_notice_channel: Channel
    cidi_ordinance: _text(200) = ""
    adhesion_state: AdhesionState = "not_requested"
    adhesion_date: date | None = None
    adhesion_file: _text(100) = ""
    system_name: _text(200) = ""
    publication_url: Annotated[
        str,
        StringConstraints(strip_whitespace=True, max_length=500, pattern=r"^(https?://\S+)?$"),
    ] = ""
    contact: _text(200) = ""
    # Secrets that are new or change; those left out stay as they are.
    secrets: Annotated[list[SecretIn], Field(max_length=MAX_SECRETS)] = []
    removed_secrets: Annotated[list[SecretName], Field(max_length=MAX_SECRETS)] = []


class SecretOut(BaseModel):
    """That a secret is there, and since when."""

    name: str
    set_at: datetime


class NoticeSettingsOut(BaseModel):
    resident_notice_channel: Channel
    cidi_ordinance: str
    adhesion_state: AdhesionState
    adhesion_date: date | None
    adhesion_file: str
    system_name: str
    publication_url: str
    contact: str
    secrets: list[SecretOut]
    # What is needed before a channel with CiDi can be chosen.
    missing: list[str]
    # Whether this installation reaches CiDi at all, and whether it can keep secrets.
    cidi_available: bool
    secrets_available: bool


def read(ctx: RequestContext) -> NoticeSettingsOut:
    settings = municipality_settings.find(ctx.db, ctx.municipality_id)
    adhesion = connection.find(ctx.db)
    values = connection.stored(ctx.db)
    plain = {name: values[name].value if name in values else "" for name in PLAIN_VALUES}
    state = adhesion.adhesion_state if adhesion else NOT_REQUESTED
    return NoticeSettingsOut(
        resident_notice_channel=settings.resident_notice_channel if settings else EMAIL_ONLY,
        cidi_ordinance=settings.cidi_ordinance if settings else "",
        adhesion_state=state,
        adhesion_date=adhesion.adhesion_date if adhesion else None,
        adhesion_file=adhesion.adhesion_file if adhesion else "",
        **plain,
        secrets=[
            SecretOut(name=row.name, set_at=row.set_at)
            for row in values.values()
            if row.encrypted is not None
        ],
        missing=connection.missing(state, plain),
        cidi_available=cidi.is_available(),
        secrets_available=secrets.is_available(),
    )


def _check(payload: NoticeSettingsIn) -> None:
    plain = {name: getattr(payload, name) for name in PLAIN_VALUES}
    missing = connection.missing(payload.adhesion_state, plain)
    if payload.resident_notice_channel != EMAIL_ONLY and missing:
        raise cidi_not_ready(missing)
    if payload.secrets and not secrets.is_available():
        raise secrets_key_missing()


def _save_adhesion(ctx: RequestContext, payload: NoticeSettingsIn) -> CidiConnection:
    fields = {
        "adhesion_state": payload.adhesion_state,
        "adhesion_date": payload.adhesion_date,
        "adhesion_file": payload.adhesion_file,
    }
    row = connection.find(ctx.db)
    if row is None:
        return create_entity(ctx, CidiConnection(**fields), fields)
    return update_entity(ctx, row, fields)


def _save_values(ctx: RequestContext, payload: NoticeSettingsIn, now: datetime) -> dict[str, Any]:
    """Save the connection's values; what the audit trail says of it, without any secret."""
    values = connection.stored(ctx.db)

    def row_of(name: str) -> CidiConnectionValue:
        row = values.get(name)
        if row is None:
            row = CidiConnectionValue(municipality_id=ctx.municipality_id, name=name, set_at=now)
            ctx.db.add(row)
            apply_audit_fields(ctx, row, creating=True)
            values[name] = row
        else:
            apply_audit_fields(ctx, row, creating=False)
        return row

    plain = {name: getattr(payload, name) for name in PLAIN_VALUES}
    for name, value in plain.items():
        row_of(name).value = value
    new = {secret.name: secret.value.get_secret_value() for secret in payload.secrets}
    removed = [
        name
        for name in dict.fromkeys(payload.removed_secrets)
        if name not in new and name in values and values[name].encrypted is not None
    ]
    for name in removed:
        ctx.db.delete(values[name])
    for name, value in new.items():
        # Whoever deletes and sets one at once changes it.
        connection.set_secret(row_of(name), ctx.municipality_id, value, now)
    ctx.db.flush()
    return plain | {"secrets_changed": sorted(new), "secrets_removed": sorted(removed)}


def save(ctx: RequestContext, row: MunicipalitySettings, payload: NoticeSettingsIn) -> None:
    """`row` is the municipality's configuration; whoever calls records its change."""
    _check(payload)
    row.resident_notice_channel = payload.resident_notice_channel
    row.cidi_ordinance = payload.cidi_ordinance
    adhesion = _save_adhesion(ctx, payload)
    changes = _save_values(ctx, payload, datetime.now(UTC))
    record_change(ctx, "update", adhesion, changes)
