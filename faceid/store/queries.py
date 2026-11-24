"""Read-only report queries (SPEC F6). The rules that turn these rows into reports live in faceid.reports.tables.

Every query takes `faculty_id`: when it is given, only that Faculty member's Subjects are included (F6.3).
"""

from datetime import date, timedelta

from faceid.store import db
from faceid.store.teaching import as_time

_RECORD = (
    "SELECT sub.subject_id, sub.subject_code, sub.subject_name, s.student_id, s.enrollment_no, s.name,"
    " a.status, a.minutes_late, TIME_TO_SEC(TIMEDIFF(c.end_time, c.start_time)) DIV 60 AS session_minutes"
    " FROM attendance a"
    " JOIN class_session c ON c.session_id = a.session_id"
    " JOIN subject sub ON sub.subject_id = c.subject_id"
    " JOIN student s ON s.student_id = a.student_id"
    " WHERE c.status = 'closed'"
)


def _scoped(sql: str, params: list, faculty_id: int | None) -> tuple[str, tuple]:
    if faculty_id is not None:
        sql += " AND sub.faculty_id = %s"
        params.append(faculty_id)
    return sql, tuple(params)


def closed_records(*, subject_id: int | None = None, student_id: int | None = None, month: date | None = None,
                   faculty_id: int | None = None) -> list[dict]:
    """Attendance Records of closed Class Sessions, filtered by Subject, Student or calendar month."""
    sql, params = _RECORD, []
    if subject_id is not None:
        sql += " AND sub.subject_id = %s"
        params.append(subject_id)
    if student_id is not None:
        sql += " AND s.student_id = %s"
        params.append(student_id)
    if month is not None:
        next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        sql += " AND c.session_date >= %s AND c.session_date < %s"
        params += [month, next_month]
    rows = db.query(*_scoped(sql, params, faculty_id))
    for row in rows:
        row["session_minutes"] = int(row["session_minutes"])  # MySQL returns DIV results as Decimal
    return rows


def records_on(day: date, faculty_id: int | None = None) -> list[dict]:
    """Every Attendance Record of every Class Session on `day`, whatever the session's status."""
    sql = (
        "SELECT sub.subject_code, sub.subject_name, c.start_time, c.end_time, c.status AS session_status,"
        " s.enrollment_no, s.name, a.status, a.minutes_late, a.method, a.confidence"
        " FROM attendance a"
        " JOIN class_session c ON c.session_id = a.session_id"
        " JOIN subject sub ON sub.subject_id = c.subject_id"
        " JOIN student s ON s.student_id = a.student_id"
        " WHERE c.session_date = %s"
    )
    rows = db.query(*_scoped(sql, [day], faculty_id))
    for row in rows:
        row["start_time"], row["end_time"] = as_time(row["start_time"]), as_time(row["end_time"])
    return rows


def session_history(student_id: int) -> list[dict]:
    """A Student's own Attendance Records, newest Class Session first."""
    rows = db.query(
        "SELECT c.session_date, c.start_time, sub.subject_code, sub.subject_name, c.status AS session_status,"
        " a.status, a.minutes_late, a.method"
        " FROM attendance a"
        " JOIN class_session c ON c.session_id = a.session_id"
        " JOIN subject sub ON sub.subject_id = c.subject_id"
        " WHERE a.student_id = %s ORDER BY c.session_date DESC, c.start_time DESC",
        (student_id,),
    )
    for row in rows:
        row["start_time"] = as_time(row["start_time"])
    return rows
