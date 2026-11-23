"""Email notifications: who is told about what, and only once.

`gobernar360 notify` runs on a schedule. For each municipality it collects the current
alerts: the platform's own (a dashboard without a status light for the month that just
ended) and those each enabled dashboard raises through `DashboardModule.get_alerts`.

Who receives them is the municipality's choice (Configuración): its list of addresses
gets every alert; with an empty list, each alert goes to its dashboard's administrators.
An address that belongs to an account which turned a kind off does not get that kind.
One email per address and kind, in the municipality's version of the text.

An alert is sent once per address and event: `notifications_sent` records it in the
same transaction as the queued email, and a second run, even a concurrent one, finds
the record and sends nothing.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gobernar360.core.config import get_settings
from gobernar360.core.db import platform_session, tenant_session
from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import Alert
from gobernar360.platform import email_templates
from gobernar360.platform.access import AccessLevel, effective_levels, enabled_dashboard_keys
from gobernar360.platform.models import (
    DashboardStatus,
    Membership,
    Municipality,
    MunicipalitySettings,
    NotificationOptOut,
    NotificationSent,
    User,
)
from gobernar360.platform.notification_kinds import STATUS_LIGHT_MISSING, all_kinds
from gobernar360.platform.texts import dashboard_name, month_name

__all__ = ["STATUS_LIGHT_MISSING", "all_kinds", "notify", "notify_municipality"]


def previous_month(today: date) -> tuple[int, int]:
    return (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)


def _status_alerts(db: Session, keys: set[str], today: date) -> list[tuple[str, Alert]]:
    year, month = previous_month(today)
    lit = set(
        db.scalars(
            select(DashboardStatus.dashboard_key).where(
                DashboardStatus.year == year, DashboardStatus.month == month
            )
        )
    )
    settings = get_settings()
    return [
        (
            key,
            Alert(
                kind=STATUS_LIGHT_MISSING,
                event_key=f"{key}:{year}-{month:02d}",
                params={"dashboard": dashboard_name(key), "link": settings.app_link(f"/d/{key}")},
            ),
        )
        for key in sorted(keys - lit)
    ]


def _alerts(db: Session, keys: set[str], today: date) -> list[tuple[str, Alert]]:
    """Current alerts of the municipality the session is scoped to, with their dashboard."""
    alerts = _status_alerts(db, keys, today)
    for key in sorted(keys):
        module = registry.get_module(key)
        if module is not None and module.get_alerts is not None:
            alerts.extend((key, alert) for alert in module.get_alerts(db, today))
    return alerts


def _claim(db: Session, municipality_id, recipient: str, alerts: list[Alert]) -> list[Alert]:
    """Record the alerts as sent to the address; return those nobody had recorded before."""
    unique = list({(alert.kind, alert.event_key): alert for alert in alerts}.values())
    claimed = set(
        db.execute(
            insert(NotificationSent)
            .values(
                [
                    {
                        "municipality_id": municipality_id,
                        "recipient": recipient,
                        "kind": alert.kind,
                        "event_key": alert.event_key,
                    }
                    for alert in unique
                ]
            )
            .on_conflict_do_nothing(
                index_elements=["municipality_id", "recipient", "kind", "event_key"]
            )
            .returning(NotificationSent.kind, NotificationSent.event_key)
        ).all()
    )
    return [alert for alert in unique if (alert.kind, alert.event_key) in claimed]


def _recipients(
    db: Session, municipality: Municipality, alerts: list[tuple[str, Alert]]
) -> dict[str, list[Alert]]:
    """The alerts each address should hear about, before opt-outs."""
    settings = db.scalar(
        select(MunicipalitySettings).where(MunicipalitySettings.municipality_id == municipality.id)
    )
    if settings is not None and settings.notification_emails:
        return {email: [alert for _, alert in alerts] for email in settings.notification_emails}
    memberships = db.scalars(
        select(Membership).where(Membership.municipality_id == municipality.id)
    ).unique()
    recipients: dict[str, list[Alert]] = {}
    for membership in memberships:
        if not membership.user.is_active:
            continue
        levels = effective_levels(db, membership)
        theirs = [alert for key, alert in alerts if levels.get(key) == AccessLevel.ADMIN]
        if theirs:
            recipients[membership.user.email] = theirs
    return recipients


def _opted_out(db: Session, email: str) -> set[str]:
    return set(
        db.scalars(
            select(NotificationOptOut.kind)
            .join(User, User.id == NotificationOptOut.user_id)
            .where(User.email == email)
        )
    )


def notify_municipality(db: Session, municipality: Municipality, today: date) -> int:
    """Queue the emails for one municipality. `db` must be scoped to it. Returns how many."""
    alerts = _alerts(db, enabled_dashboard_keys(db, municipality.id), today)
    if not alerts:
        return 0
    year, month = previous_month(today)
    params = {
        "municipality": municipality.name,
        "month": month_name(month),
        "account_link": get_settings().app_link("/account"),
    }
    queued = 0
    for email, theirs in sorted(_recipients(db, municipality, alerts).items()):
        opted_out = _opted_out(db, email)
        wanted = [alert for alert in theirs if alert.kind not in opted_out]
        by_kind: dict[str, list[Alert]] = defaultdict(list)
        for alert in _claim(db, municipality.id, email, wanted) if wanted else []:
            by_kind[alert.kind].append(alert)
        for kind, kind_alerts in by_kind.items():
            items = email_templates.items_list(kind, [alert.params for alert in kind_alerts])
            email_templates.send(db, email, municipality.id, kind, items=items, **params)
            queued += 1
    return queued


@dataclass
class NotifyReport:
    municipalities: int = 0
    emails: int = 0


def notify(today: date) -> NotifyReport:
    """Queue notification emails for every municipality, each in its own transaction."""
    with platform_session() as db:
        municipalities = list(db.scalars(select(Municipality).order_by(Municipality.name)))
    report = NotifyReport()
    for municipality in municipalities:
        with tenant_session(municipality.id) as db:
            report.emails += notify_municipality(db, municipality, today)
        report.municipalities += 1
    return report
