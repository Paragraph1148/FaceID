"""F7.1 and SPEC §4: `flask db-upgrade` builds the synopsis schema with the agreed changes."""

from faceid.store import db

# SPEC §4: the synopsis's seven tables, minus face_encoding.image_path, plus the ADR columns.
EXPECTED_COLUMNS = {
    "admin": {"admin_id", "username", "password_hash", "email", "created_at"},
    "student": {
        "student_id", "enrollment_no", "name", "email", "mobile", "course", "semester",
        "section", "photo_path", "is_active", "password_hash", "must_change_password",
    },
    "face_encoding": {"encoding_id", "student_id", "encoding_vector", "captured_at"},
    "faculty": {
        "faculty_id", "name", "email", "password_hash", "department", "must_change_password", "is_active",
    },
    "subject": {"subject_id", "subject_code", "subject_name", "semester", "faculty_id", "course", "is_active"},
    "class_session": {
        "session_id", "subject_id", "faculty_id", "session_date", "start_time", "end_time", "room_no", "status",
    },
    "attendance": {
        "attendance_id", "session_id", "student_id", "status", "marked_at", "confidence", "method", "minutes_late",
    },
}


def columns_by_table(app):
    with app.app_context():
        rows = db.query(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = %s",
            (app.config["DB_NAME"],),
        )
    tables = {}
    for row in rows:
        tables.setdefault(row["TABLE_NAME"], set()).add(row["COLUMN_NAME"])
    tables.pop("schema_migrations", None)
    return tables


def test_upgrade_on_a_fresh_server_creates_exactly_the_spec_schema(empty_app, cli):
    result = cli.invoke(args=["db-upgrade"])

    assert result.exit_code == 0, result.output
    assert columns_by_table(empty_app) == EXPECTED_COLUMNS


def test_upgrade_twice_is_safe(empty_app, cli):
    cli.invoke(args=["db-upgrade"])
    second = cli.invoke(args=["db-upgrade"])

    assert second.exit_code == 0, second.output
    assert "up to date" in second.output
    assert columns_by_table(empty_app) == EXPECTED_COLUMNS


def test_pages_refuse_to_serve_until_the_database_is_upgraded(empty_app):
    response = empty_app.test_client().get("/login")

    assert response.status_code == 503
    assert b"flask db-upgrade" in response.data
