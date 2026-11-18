"""Command-line administration tasks."""

from typing import Annotated

import typer
from sqlalchemy import select

from gobernar360.core.db import platform_session
from gobernar360.core.security import hash_password, normalize_email
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
    """Load demo municipalities, users and projects. Never run this against real data."""
    from gobernar360.seed import DEMO_PASSWORD
    from gobernar360.seed import seed_demo as load_demo

    if load_demo(reset=reset):
        typer.echo(f"Demo data loaded. Every demo account uses the password: {DEMO_PASSWORD}")
    else:
        typer.echo("Demo data already present; nothing changed.")
