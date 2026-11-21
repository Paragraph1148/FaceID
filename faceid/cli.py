"""`flask` commands for setup and operations (SPEC F1.2, F7)."""

import click
from mysql.connector import IntegrityError
from flask import current_app
from flask.cli import with_appcontext

from faceid.passwords import problem_with
from faceid.store import db, people


@click.command("db-upgrade")
@with_appcontext
def db_upgrade():
    """Create the database and apply pending schema migrations."""
    applied = db.upgrade(current_app.config)
    if applied:
        for name in applied:
            click.echo(f"applied {name}")
    else:
        click.echo("database is up to date")




@click.command("create-admin")
@click.option("--username", prompt="Admin username")
@click.option("--email", prompt="Admin email")
@click.password_option("--password", prompt="Password")
@with_appcontext
def create_admin(username, email, password):
    """Create an Admin account. There is no default account (SPEC F1.2)."""
    error = problem_with(password)
    if error:
        raise click.ClickException(error)
    if people.email_owner(email.strip()):
        raise click.ClickException(f"{email} is already used by another account.")
    try:
        people.create_admin(username.strip(), email.strip(), password)
    except IntegrityError:
        raise click.ClickException(f"The username {username.strip()} is already taken.") from None
    click.echo(f"Admin {email} created.")


def register(app):
    app.cli.add_command(db_upgrade)
    app.cli.add_command(create_admin)
