"""Command-line administration tasks."""

import re
from typing import Annotated

import typer
from sqlalchemy import select

from gobernar360.core.db import platform_session
from gobernar360.core.security import hash_password, normalize_email
from gobernar360.platform.clock import get_today
from gobernar360.platform.models import User
from gobernar360.platform.schemas import MIN_PASSWORD_LENGTH

app = typer.Typer(no_args_is_help=True, help="gobernar360 administration commands.")


@app.callback()
def main() -> None:
    """Keeps sub-commands explicit even while there is only one."""


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


def _month_option(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{2})", value.strip())
    if match is None or not 1 <= int(match[2]) <= 12:
        raise typer.BadParameter("Use the form YYYY-MM, e.g. 2026-01.")
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
    from gobernar360.main import install_dashboards
    from gobernar360.platform.snapshots import take_snapshots

    install_dashboards()
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
