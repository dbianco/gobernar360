"""Command-line administration tasks."""

import logging
import time
from typing import Annotated

import typer
from sqlalchemy import select

from gobernar360.core.config import get_settings
from gobernar360.core.db import platform_session
from gobernar360.core.security import hash_password, normalize_email
from gobernar360.platform import outbox
from gobernar360.platform.models import User
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
