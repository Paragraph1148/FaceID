"""F7.2: `flask backup <file>` and `flask restore <file>` (faceid.store.backup), against real MySQL."""

import json
from datetime import date, datetime, time

import numpy as np
import pytest

from conftest import create_admin

from faceid.store import attendance, backup, db, people, teaching


@pytest.fixture
def filled(app):
    """One of everything, including Face Encodings, times, dates and NULLs."""
    create_admin(app)
    with app.app_context():
        sharma = people.create_faculty("R. Sharma", "sharma@college.test", "CA", "temp-pass-1")
        ml = teaching.create_subject("CA261481", "Machine Learning", "MCA", 1, sharma)
        asha = people.create_student("SSPU20260001", "Asha Verma", "asha@college.test", None, "MCA", 1, "A")
        people.replace_encodings(asha, [np.linspace(-0.5, 0.5, 128), np.full(128, 0.125)])
        session_id = attendance.open_class_session(sharma, ml, date(2026, 12, 1), time(10, 0), time(11, 0), "204")
        attendance.override(session_id, asha, "late", 15, at=datetime(2026, 12, 1, 10, 15))
        attendance.close(session_id)
    return app


def everything(app) -> dict:
    with app.app_context():
        return {table: db.query(f"SELECT * FROM {table}") for table in backup.TABLES}


def test_a_backup_restores_every_row_exactly(filled, tmp_path):
    before = everything(filled)
    path = tmp_path / "faceid-backup.json"
    cli = filled.test_cli_runner()

    assert cli.invoke(args=["backup", str(path)]).exit_code == 0
    with filled.app_context():  # a reinstall: an empty, upgraded database
        db.drop_database(filled.config)
        db.upgrade(filled.config)
    result = cli.invoke(args=["restore", str(path), "--yes"])

    assert result.exit_code == 0, result.output
    assert everything(filled) == before
    with filled.app_context():
        encodings = people.encodings_of_other_students(0)
    assert np.array_equal(next(iter(encodings.values()))[0], np.linspace(-0.5, 0.5, 128))


def test_restoring_replaces_what_was_there(filled, tmp_path):
    path = tmp_path / "backup.json"
    cli = filled.test_cli_runner()
    cli.invoke(args=["backup", str(path)])
    with filled.app_context():
        people.create_student("SSPU20260099", "Added Later", None, None, "MCA", 1, None)

    cli.invoke(args=["restore", str(path), "--yes"])

    with filled.app_context():
        assert [s["enrollment_no"] for s in people.list_students()] == ["SSPU20260001"]


def test_the_backup_holds_encodings_but_no_images(filled, tmp_path):
    path = tmp_path / "backup.json"
    filled.test_cli_runner().invoke(args=["backup", str(path)])

    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data["tables"]) == set(backup.TABLES)
    assert len(data["tables"]["face_encoding"]["rows"]) == 2
    assert all(row[data["tables"]["student"]["columns"].index("photo_path")] is None for row in data["tables"]["student"]["rows"])


def test_restore_asks_before_replacing_the_database(filled, tmp_path):
    path = tmp_path / "backup.json"
    cli = filled.test_cli_runner()
    cli.invoke(args=["backup", str(path)])
    with filled.app_context():
        people.create_student("SSPU20260099", "Added Later", None, None, "MCA", 1, None)

    result = cli.invoke(args=["restore", str(path)], input="n\n")

    assert result.exit_code != 0
    with filled.app_context():
        assert len(people.list_students()) == 2


def test_a_damaged_backup_changes_nothing(filled, tmp_path):
    path = tmp_path / "backup.json"
    cli = filled.test_cli_runner()
    cli.invoke(args=["backup", str(path)])
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tables"]["attendance"]["rows"][0][0] = "not a number"
    path.write_text(json.dumps(data), encoding="utf-8")
    before = everything(filled)

    result = cli.invoke(args=["restore", str(path), "--yes"])

    assert result.exit_code != 0
    assert everything(filled) == before


@pytest.mark.parametrize("damage, message", [
    (lambda data: data.update(schema=data["schema"] + 1), "schema version"),
    (lambda data: data["tables"]["student"]["columns"].append("favourite_colour"), "student"),
    (lambda data: data.update(format="something else"), "not a FaceID backup"),
])
def test_a_backup_that_does_not_fit_this_schema_is_refused(filled, tmp_path, damage, message):
    path = tmp_path / "backup.json"
    cli = filled.test_cli_runner()
    cli.invoke(args=["backup", str(path)])
    data = json.loads(path.read_text(encoding="utf-8"))
    damage(data)
    path.write_text(json.dumps(data), encoding="utf-8")

    result = cli.invoke(args=["restore", str(path), "--yes"])

    assert result.exit_code != 0 and message in result.output
