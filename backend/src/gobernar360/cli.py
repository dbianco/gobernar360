"""Command-line administration tasks."""

import logging
import re
import time
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select

from gobernar360.core.config import get_settings
from gobernar360.core.db import platform_session, tenant_session
from gobernar360.core.security import hash_password, normalize_email
from gobernar360.platform import cidi, notice_delivery, outbox
from gobernar360.platform.access import system_context
from gobernar360.platform.cidi import CidiNotConfigured
from gobernar360.platform.clock import get_now, get_today
from gobernar360.platform.models import User
from gobernar360.platform.notice_delivery import NoticeReport
from gobernar360.platform.schemas import MIN_PASSWORD_LENGTH

app = typer.Typer(no_args_is_help=True, help="gobernar360 administration commands.")


@app.callback()
def main() -> None:
    """Keeps sub-commands explicit."""


@app.command()
def create_operator(
    email: Annotated[str, typer.Option(help="Email the operator signs in with.")],
    full_name: Annotated[str, typer.Option(help="Operator's full name.")],
    password: Annotated[str, typer.Option(prompt=True, confirmation_prompt=True, hide_input=True)],
) -> None:
    """Create a platform operator, who manages municipalities and their dashboards."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise typer.BadParameter(f"Password must have at least {MIN_PASSWORD_LENGTH} characters.")
    normalized = normalize_email(email)
    with platform_session() as db:
        if db.scalar(select(User.id).where(User.email == normalized)):
            raise typer.BadParameter(f"A user with email {normalized} already exists.")
        db.add(
            User(
                email=normalized,
                full_name=full_name,
                password_hash=hash_password(password),
                is_platform_operator=True,
            )
        )
    typer.echo(f"Operator {normalized} created.")


@app.command()
def seed_demo(
    reset: Annotated[
        bool, typer.Option("--reset", help="Delete ALL existing data before loading the demo.")
    ] = False,
) -> None:
    """Load demo municipalities, users and dashboard data. Never run this against real data."""
    from gobernar360.seed import DEMO_PASSWORD
    from gobernar360.seed import seed_demo as load_demo

    if load_demo(reset=reset):
        typer.echo(f"Demo data loaded. Every demo account uses the password: {DEMO_PASSWORD}")
    else:
        typer.echo("Demo data already present; nothing changed.")


def _deliver(due_only: bool) -> outbox.DeliveryReport:
    settings = get_settings()
    return outbox.deliver(outbox.SmtpTransport(settings), settings.email_from, due_only=due_only)


@app.command()
def send_email(
    watch: Annotated[
        bool, typer.Option("--watch", help="Keep running and deliver new emails as they come.")
    ] = False,
    interval: Annotated[float, typer.Option(help="Seconds between checks with --watch.")] = 5,
    retry_failed: Annotated[
        bool, typer.Option("--retry-failed", help="Retry emails that ran out of attempts.")
    ] = False,
) -> None:
    """Deliver the emails waiting in the outbox over SMTP.

    Once: sends everything pending now, including emails waiting for a retry. With
    --watch: keeps running, and retries failed deliveries with growing delays.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if retry_failed:
        typer.echo(f"{outbox.requeue_failed()} failed emails queued again.")
    if not watch:
        report = _deliver(due_only=False)
        typer.echo(
            f"Sent: {report.sent}. Will be retried: {report.retrying}. Failed: {report.failed}."
        )
        if report.retrying or report.failed:
            raise typer.Exit(1)
        return
    typer.echo(f"Delivering emails every {interval:g} s. Ctrl+C stops.")
    try:
        while True:
            report = _deliver(due_only=True)
            if report.attempted:
                typer.echo(
                    f"Sent: {report.sent}. Will be retried: {report.retrying}. "
                    f"Failed: {report.failed}."
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        typer.echo("Stopped.")


def _hand_over(due_only: bool) -> NoticeReport | None:
    """Deliver what is queued for CiDi, saying how it went when there was anything."""
    try:
        report = notice_delivery.deliver(due_only=due_only)
    except CidiNotConfigured as error:
        typer.echo(f"Nothing was sent. {error}", err=True)
        raise typer.Exit(code=1) from error
    if report is not None and (not due_only or report.attempted or report.unreadable):
        typer.echo(
            f"Handed over: {report.handed_over}. Will be retried: {report.retrying}. "
            f"Failed: {report.failed} ({report.emailed} emailed instead)."
        )
        if report.unreadable:
            typer.echo(
                f"{report.unreadable} municipalities have a connection that cannot be "
                "decrypted: check GOBERNAR360_SECRETS_KEY.",
                err=True,
            )
    return report


@app.command()
def send_notices(
    watch: Annotated[
        bool, typer.Option("--watch", help="Keep running and deliver new notices as they come.")
    ] = False,
    interval: Annotated[float, typer.Option(help="Seconds between checks with --watch.")] = 30,
) -> None:
    """Hand the notices waiting for CiDi over to it.

    Once: tries everything pending now, including notices waiting for a retry. With
    --watch: keeps running, and retries with growing delays. Notices by email go out with
    send-email.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    report = _hand_over(due_only=watch)
    if report is None:
        typer.echo("CiDi is off (GOBERNAR360_CIDI_MODE): nothing is sent through it.")
        return
    if not watch:
        if report.retrying or report.failed or report.unreadable:
            raise typer.Exit(1)
        return
    typer.echo(f"Delivering notices every {interval:g} s. Ctrl+C stops.")
    try:
        while True:
            time.sleep(interval)
            _hand_over(due_only=True)
    except KeyboardInterrupt:
        typer.echo("Stopped.")


@app.command()
def cidi_fake_inbox() -> None:
    """Show what was handed over to the fake CiDi (GOBERNAR360_CIDI_MODE=fake)."""
    inbox = cidi.fake_inbox()
    messages = inbox.messages()
    if not messages:
        typer.echo(f"There is nothing in {inbox.path}.")
    for message in messages:
        typer.echo(f"To {message['recipient_cuil']}: {message['subject']}")
        typer.echo(message["body"])


@app.command()
def notify(
    send: Annotated[bool, typer.Option(help="Also deliver the queued emails right away.")] = True,
) -> None:
    """Email administrators about overdue milestones and missing status lights.

    Run it on a schedule, e.g. daily: each event is emailed once to each person, however
    many times the command runs.
    """
    from gobernar360.main import register_dashboards
    from gobernar360.platform import notifications
    from gobernar360.platform.clock import get_today

    register_dashboards()
    report = notifications.notify(get_today())
    typer.echo(
        f"Notification emails queued: {report.emails} "
        f"({report.municipalities} municipalities checked)."
    )
    if send and report.emails:
        delivery = _deliver(due_only=True)
        typer.echo(f"Sent: {delivery.sent}. Will be retried: {delivery.retrying}.")


# No municipality has data older than this; rebuilding from year 1 would take hours.
FIRST_YEAR = 2000


def _month_option(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{2})", value.strip())
    if match is None or not 1 <= int(match[2]) <= 12:
        raise typer.BadParameter("Use the form YYYY-MM, e.g. 2026-01.")
    if int(match[1]) < FIRST_YEAR:
        raise typer.BadParameter(f"The earliest month that can be rebuilt is {FIRST_YEAR}-01.")
    return int(match[1]), int(match[2])


@app.command()
def snapshot_indicators(
    since: Annotated[
        str | None,
        typer.Option(
            "--from",
            help="Also rebuild the closed months since this one (YYYY-MM), for the "
            "indicators that can be rebuilt. The others are never filled in afterwards.",
            callback=_month_option,
        ),
    ] = None,
) -> None:
    """Record this month's headline indicators for every municipality.

    Run it daily, or at least on each month's last day: a month keeps its last run.
    Safe to repeat.
    """
    from gobernar360.main import register_dashboards
    from gobernar360.platform.snapshots import take_snapshots

    register_dashboards()
    today = get_today()
    if since is not None and since > (today.year, today.month):
        raise typer.BadParameter("The month has not started yet.", param_hint="--from")
    report = take_snapshots(today, since)
    year, month = report.month
    typer.echo(f"Snapshot of {year}-{month:02d} taken for {report.municipalities} municipalities.")
    if report.rebuilt:
        first, last = report.rebuilt[0], report.rebuilt[-1]
        typer.echo(f"Rebuilt {first[0]}-{first[1]:02d} to {last[0]}-{last[1]:02d}.")
    typer.echo(f"{report.changed_rows} rows written or changed.")
    if report.failed:
        typer.echo(f"Failed, left unchanged: {', '.join(report.failed)}", err=True)
        raise typer.Exit(code=1)


@app.command()
def assign_zones() -> None:
    """Work out again the zones of every record of every municipality.

    The database keeps them up to date by itself; this is for after loading data with its
    triggers off, e.g. restoring a backup. Running it twice changes nothing more.
    """
    from gobernar360.platform.geo.assignment import reassign
    from gobernar360.platform.models import Municipality

    with platform_session() as db:
        municipalities = db.execute(
            select(Municipality.id, Municipality.name).order_by(Municipality.name)
        ).all()
    for municipality_id, name in municipalities:
        changed = reassign(municipality_id)
        typer.echo(f"{name}: {changed.added} assignments added, {changed.removed} removed.")


@app.command()
def import_idecor(
    slug: Annotated[str, typer.Argument(help="The municipality, e.g. noetinger.")],
    radius: Annotated[
        bool, typer.Option("--radius", help='Create or move the zone "Radio urbano".')
    ] = False,
    layers: Annotated[
        str, typer.Option(help="Facilities to bring in, by commas: health,schools.")
    ] = "",
    from_dir: Annotated[
        Path | None,
        typer.Option(
            help="Read saved answers from this directory instead of the service, as "
            "docs/idecor/samples has them.",
            exists=True,
            file_okay=False,
        ),
    ] = None,
) -> None:
    """Bring in a municipality's official geography from IDECOR (Province of Córdoba).

    Safe to repeat: what did not change is left as it is. Any failure leaves everything as
    it was.
    """
    from gobernar360.platform.geo import idecor
    from gobernar360.platform.geo.reference_import import LAYERS, import_official
    from gobernar360.platform.models import Municipality

    wanted = list(dict.fromkeys(part.strip() for part in layers.split(",") if part.strip()))
    unknown = [layer for layer in wanted if layer not in LAYERS]
    if unknown:
        raise typer.BadParameter(
            f"Unknown: {', '.join(unknown)}. There are: {', '.join(LAYERS)}.",
            param_hint="--layers",
        )
    if not radius and not wanted:
        raise typer.BadParameter("Nothing to import: use --radius, --layers or both.")
    with platform_session() as db:
        municipality = db.scalar(select(Municipality).where(Municipality.slug == slug))
    if municipality is None:
        raise typer.BadParameter(f"There is no municipality {slug}.", param_hint="SLUG")
    source = idecor.Directory(from_dir, slug) if from_dir else idecor.Wfs()
    try:
        with tenant_session(municipality.id) as db:
            report = import_official(
                system_context(db, municipality.id),
                source,
                radius=radius,
                layers=wanted,
                now=get_now(),
            )
    except idecor.IdecorError as error:
        typer.echo(f"Nothing was changed. {error}", err=True)
        raise typer.Exit(code=1) from error

    sources = [*([report.radius] if report.radius else []), *report.layers]
    if report.radius:
        found = report.radius
        law = f" ({found.law})" if found.law else ""
        typer.echo(f"Radio urbano: 1 zone {found.change}, {found.area_ha:.1f} ha{law}.")
        for overlap in found.overlaps:
            typer.echo(
                f"  Warning: {overlap.zone.name} and {overlap.other.name} share "
                f"{overlap.area_m2 / 10_000:.2f} ha."
            )
    for layer in report.layers:
        typer.echo(
            f"{layer.layer}: {layer.read} features read; {layer.created} created, "
            f"{layer.moved} moved or changed, {layer.unchanged} unchanged, "
            f"{layer.removed} removed; {layer.skipped} skipped, "
            f"{layer.outside} outside the radius."
        )
    typer.echo("Source: IDECOR, Infraestructura de Datos Espaciales de la Provincia de Córdoba.")
    for item in sources:
        typer.echo(f"  {item.source}")
        if item.srid == idecor.DEGREES_SRID:
            typer.echo("  Warning: in degrees, which IDECOR rounds to about 10 m.")
    typer.echo(f"Read on {get_today():%Y-%m-%d}.")
