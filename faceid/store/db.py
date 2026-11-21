"""MySQL connection, queries and schema migrations.

One connection per request, kept on Flask's `g`. Queries return rows as dicts.
"""

from pathlib import Path

import mysql.connector
from flask import current_app, g

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _connect(config, with_database: bool = True):
    return mysql.connector.connect(
        host=config["DB_HOST"],
        port=config["DB_PORT"],
        user=config["DB_USER"],
        password=config["DB_PASSWORD"],
        database=config["DB_NAME"] if with_database else None,
        autocommit=False,
    )


def connection():
    if "db" not in g:
        g.db = _connect(current_app.config)
    return g.db


def close(_error: BaseException | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query(sql: str, params: tuple = ()) -> list[dict]:
    cursor = connection().cursor(dictionary=True)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()) -> int:
    """Run one statement and commit. Returns the new row id for INSERTs."""
    conn = connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    return new_id


def duplicate_field(error: Exception) -> str | None:
    """For a duplicate-key IntegrityError, the column that clashed (e.g. "email"); otherwise None.

    MySQL reports it as: Duplicate entry 'x' for key 'student.enrollment_no'.
    """
    if getattr(error, "errno", None) != 1062:
        return None
    key = str(error.msg).rsplit("for key '", 1)[-1].rstrip("'")
    return key.split(".")[-1]


def drop_database(config) -> None:
    conn = _connect(config, with_database=False)
    conn.cursor().execute(f"DROP DATABASE IF EXISTS `{config['DB_NAME']}`")
    conn.close()


# --- Migrations -------------------------------------------------------------


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def _statements(sql_text: str) -> list[str]:
    # Our migrations are plain DDL, so splitting on ";" is safe. Comment lines are dropped first.
    lines = [line for line in sql_text.splitlines() if not line.strip().startswith("--")]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]


def _applied_versions(cursor) -> set[int]:
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version INT PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    cursor.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}


def upgrade(config) -> list[str]:
    """Create the database if needed and apply pending migrations. Returns the names applied."""
    server = _connect(config, with_database=False)
    server.cursor().execute(
        f"CREATE DATABASE IF NOT EXISTS `{config['DB_NAME']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    server.close()

    conn = _connect(config)
    cursor = conn.cursor()
    applied = _applied_versions(cursor)
    newly_applied = []
    for path in _migration_files():
        version = int(path.name[:4])
        if version in applied:
            continue
        for statement in _statements(path.read_text(encoding="utf-8")):
            cursor.execute(statement)
        cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        conn.commit()
        newly_applied.append(path.name)
    conn.close()
    return newly_applied


def is_up_to_date(config) -> bool:
    """True when every migration file has been applied."""
    latest = int(_migration_files()[-1].name[:4])
    try:
        conn = _connect(config)
    except mysql.connector.errors.ProgrammingError:
        return False  # database does not exist yet
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s AND table_name = 'schema_migrations'",
        (config["DB_NAME"],),
    )
    if cursor.fetchone()[0] == 0:
        conn.close()
        return False
    cursor.execute("SELECT MAX(version) FROM schema_migrations")
    current = cursor.fetchone()[0] or 0
    conn.close()
    return current >= latest
