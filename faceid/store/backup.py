"""Backup and restore (SPEC F7.2): every row of the seven tables, as one JSON file.

Written in Python rather than with `mysqldump`, so it works on Windows without extra installs (DESIGN).
The file holds names and Face Encodings, never face images (N3), so it is personal data: keep it out of git.
"""

import base64
from datetime import date, datetime, timedelta

from faceid.store import db

FORMAT = "faceid-backup"
TABLES = ("admin", "faculty", "student", "face_encoding", "subject", "class_session", "attendance")  # parents first


class BackupError(Exception):
    """The file can't be restored into this database; the message says why."""


def _encode(value: object) -> object:
    """A JSON-safe form of one column value. Types JSON lacks are tagged so they come back as the same type."""
    if isinstance(value, (bytes, bytearray)):
        return {"bytes": base64.b64encode(value).decode("ascii")}
    if isinstance(value, datetime):
        return {"datetime": value.isoformat()}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    if isinstance(value, timedelta):  # TIME columns
        return {"seconds": value.total_seconds()}
    return value


def _decode(value: object) -> object:
    if not isinstance(value, dict):
        return value
    (kind, text), = value.items()
    if kind == "bytes":
        return base64.b64decode(text)
    if kind == "datetime":
        return datetime.fromisoformat(text)
    if kind == "date":
        return date.fromisoformat(text)
    if kind == "seconds":
        return timedelta(seconds=text)
    raise BackupError(f"Unknown value in the backup: {kind}")


def _schema_version() -> int:
    return db.query_one("SELECT MAX(version) AS version FROM schema_migrations")["version"]


def _columns(table: str) -> list[str]:
    rows = db.query(
        "SELECT column_name AS name FROM information_schema.columns"
        " WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position",
        (table,),
    )
    return [row["name"] for row in rows]


def dump() -> dict:
    """Every row of every table, with the schema version they belong to."""
    tables = {}
    for table in TABLES:
        columns = _columns(table)
        rows = db.query(f"SELECT {', '.join(columns)} FROM {table}")
        tables[table] = {"columns": columns, "rows": [[_encode(row[c]) for c in columns] for row in rows]}
    return {"format": FORMAT, "schema": _schema_version(), "created_at": datetime.now().isoformat(timespec="seconds"),
            "tables": tables}


def summary(data: dict) -> str:
    """e.g. "1 admin, 3 faculty, ...": how many rows of each table the backup holds."""
    return ", ".join(f"{len(data['tables'][table]['rows'])} {table}" for table in TABLES)


def check(data: dict) -> None:
    """Raise BackupError unless `data` is a FaceID backup of exactly this database's schema."""
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("tables"), dict):
        raise BackupError("This is not a FaceID backup file.")
    current = _schema_version()
    if data.get("schema") != current:
        raise BackupError(f"The backup has schema version {data.get('schema')}, but this database has {current}. "
                          "Restore it with the FaceID release it was made with.")
    for table in TABLES:
        content = data["tables"].get(table)
        columns = _columns(table)
        # Column names are checked against the database, so a file can't smuggle SQL in through them.
        if (not isinstance(content, dict) or content.get("columns") != columns or not isinstance(content.get("rows"), list)
                or any(not isinstance(row, list) or len(row) != len(columns) for row in content["rows"])):
            raise BackupError(f"The backup's {table} table doesn't match this database.")


def restore(data: dict) -> None:
    """Replace every row in the database with the backup's, all at once: on any error nothing changes."""
    check(data)
    with db.transaction() as cursor:
        # Children are deleted first and parents inserted first, so the foreign keys stay checked throughout.
        for table in reversed(TABLES):
            cursor.execute(f"DELETE FROM {table}")
        for table in TABLES:
            columns, rows = data["tables"][table]["columns"], data["tables"][table]["rows"]
            if rows:
                placeholders = ", ".join(["%s"] * len(columns))
                cursor.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                                   [tuple(_decode(value) for value in row) for row in rows])
