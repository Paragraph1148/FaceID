"""`flask` commands for setup and operations (SPEC F1.2, F7)."""

import json

import click
from mysql.connector import IntegrityError
from flask import current_app
from flask.cli import with_appcontext

from faceid.passwords import problem_with
from faceid.store import backup, db, people


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


@click.command("backup")
@click.argument("file", type=click.Path(dir_okay=False, writable=True))
@with_appcontext
def backup_command(file):
    """Save every row of the database (Face Encodings included) to FILE, as JSON (F7.2)."""
    data = backup.dump()
    with open(file, "w", encoding="utf-8") as out:
        json.dump(data, out)
    rows = ", ".join(f"{count} {table}" for table, count in backup.counts(data).items())
    click.echo(f"Saved {rows} to {file}.")
    click.echo("It holds names and Face Encodings: keep it private and out of git.")


@click.command("restore")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--yes", is_flag=True, help="Don't ask before replacing the database.")
@with_appcontext
def restore_command(file, yes):
    """Replace everything in the database with the backup in FILE (F7.2). Stop the server first."""
    try:
        with open(file, encoding="utf-8") as source:
            data = json.load(source)
        backup.check(data)
    except (ValueError, backup.BackupError) as problem:  # json.JSONDecodeError is a ValueError
        raise click.ClickException(str(problem)) from None
    if not yes:
        click.confirm(f"Replace everything in the database {current_app.config['DB_NAME']} with {file}?", abort=True)
    try:
        backup.restore(data)
    except Exception as problem:
        raise click.ClickException(f"Nothing was changed: the backup could not be loaded ({problem}).") from None
    rows = ", ".join(f"{count} {table}" for table, count in backup.counts(data).items())
    click.echo(f"Restored {rows}.")


def register(app):
    app.cli.add_command(db_upgrade)
    app.cli.add_command(create_admin)
    app.cli.add_command(backup_command)
    app.cli.add_command(restore_command)
