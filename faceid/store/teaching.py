"""Subjects and Class Sessions (SPEC F2, F5)."""

from datetime import datetime, time, timedelta

from faceid.attendance import minutes_between
from faceid.store import db


def list_subjects() -> list[dict]:
    return db.query(
        "SELECT s.subject_id, s.subject_code, s.subject_name, s.course, s.semester, s.is_active,"
        " f.name AS faculty_name FROM subject s JOIN faculty f ON f.faculty_id = s.faculty_id"
        " ORDER BY s.is_active DESC, s.course, s.semester, s.subject_code"
    )


def get_subject(subject_id: int) -> dict | None:
    return db.query_one("SELECT * FROM subject WHERE subject_id = %s", (subject_id,))


def create_subject(subject_code: str, subject_name: str, course: str, semester: int, faculty_id: int) -> int:
    return db.execute(
        "INSERT INTO subject (subject_code, subject_name, course, semester, faculty_id) VALUES (%s, %s, %s, %s, %s)",
        (subject_code, subject_name, course, semester, faculty_id),
    )


def update_subject(subject_id: int, subject_code: str, subject_name: str, course: str, semester: int, faculty_id: int) -> None:
    db.execute(
        "UPDATE subject SET subject_code = %s, subject_name = %s, course = %s, semester = %s, faculty_id = %s"
        " WHERE subject_id = %s",
        (subject_code, subject_name, course, semester, faculty_id, subject_id),
    )


def set_subject_active(subject_id: int, active: bool) -> None:
    db.execute("UPDATE subject SET is_active = %s WHERE subject_id = %s", (active, subject_id))


def subjects_taught_by(faculty_id: int) -> list[dict]:
    """The Faculty member's active Subjects, the ones they can hold Class Sessions for."""
    return db.query(
        "SELECT subject_id, subject_code, subject_name, course, semester FROM subject"
        " WHERE faculty_id = %s AND is_active ORDER BY course, semester, subject_code",
        (faculty_id,),
    )


# --- Class Sessions (F5) ---

_SESSION_SELECT = (
    "SELECT c.session_id, c.subject_id, c.faculty_id, c.session_date, c.start_time, c.end_time, c.room_no, c.status,"
    " s.subject_code, s.subject_name, s.course, s.semester, f.name AS faculty_name,"
    " (SELECT COUNT(*) FROM attendance a WHERE a.session_id = c.session_id) AS expected,"
    " (SELECT COUNT(*) FROM attendance a WHERE a.session_id = c.session_id AND a.status <> 'absent') AS attended"
    " FROM class_session c JOIN subject s ON s.subject_id = c.subject_id JOIN faculty f ON f.faculty_id = c.faculty_id"
)


def _as_time(value: timedelta | time) -> time:
    # mysql-connector returns TIME columns as timedelta.
    return (datetime.min + value).time() if isinstance(value, timedelta) else value


def _with_times(row: dict | None) -> dict | None:
    """Add `starts_at` (a datetime) and `session_minutes`, which the attendance rules need."""
    if row is None:
        return None
    row["start_time"], row["end_time"] = _as_time(row["start_time"]), _as_time(row["end_time"])
    row["starts_at"] = datetime.combine(row["session_date"], row["start_time"])
    row["session_minutes"] = minutes_between(row["start_time"], row["end_time"])
    return row


def get_class_session(session_id: int) -> dict | None:
    return _with_times(db.query_one(f"{_SESSION_SELECT} WHERE c.session_id = %s", (session_id,)))


def list_class_sessions(faculty_id: int) -> list[dict]:
    rows = db.query(f"{_SESSION_SELECT} WHERE c.faculty_id = %s ORDER BY c.session_date DESC, c.start_time DESC", (faculty_id,))
    return [_with_times(row) for row in rows]


def find_open_class_session() -> dict | None:
    """The server's one open Class Session (F5.2), if any."""
    return _with_times(db.query_one(f"{_SESSION_SELECT} WHERE c.status = 'open' ORDER BY c.session_id LIMIT 1"))
