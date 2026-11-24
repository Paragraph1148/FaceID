"""Read-only report queries (SPEC F6). The rules that turn these rows into reports live in faceid.reports.tables.

Queries that take `faculty_id` return, when it is given, only the Class Sessions that Faculty member held
(F6.3). That follows the sessions, not the Subject's current owner, so reassigning a Subject moves no history.
"""

from datetime import date, timedelta

from faceid.attendance import minutes_between
from faceid.store import db
from faceid.store.teaching import as_time

_RECORDS = (
    " FROM attendance a"
    " JOIN class_session c ON c.session_id = a.session_id"
    " JOIN subject sub ON sub.subject_id = c.subject_id"
    " JOIN student s ON s.student_id = a.student_id"
)


def _query(select: str, where: list[str], params: list, faculty_id: int | None, order: str = "") -> list[dict]:
    if faculty_id is not None:
        where.append("c.faculty_id = %s")
        params.append(faculty_id)
    rows = db.query(f"SELECT {select}{_RECORDS} WHERE {' AND '.join(where)}{order}", tuple(params))
    for row in rows:
        row["start_time"], row["end_time"] = as_time(row["start_time"]), as_time(row["end_time"])
    return rows


def closed_records(*, subject_id: int | None = None, student_id: int | None = None, month: date | None = None,
                   faculty_id: int | None = None) -> list[dict]:
    """Attendance Records of closed Class Sessions, filtered by Subject, Student or calendar month."""
    where, params = ["c.status = 'closed'"], []
    if subject_id is not None:
        where.append("sub.subject_id = %s")
        params.append(subject_id)
    if student_id is not None:
        where.append("s.student_id = %s")
        params.append(student_id)
    if month is not None:
        next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
        where.append("c.session_date >= %s AND c.session_date < %s")
        params += [month, next_month]
    rows = _query("sub.subject_id, sub.subject_code, sub.subject_name, s.student_id, s.enrollment_no, s.name,"
                  " a.status, a.minutes_late, c.start_time, c.end_time", where, params, faculty_id)
    for row in rows:
        row["session_minutes"] = minutes_between(row["start_time"], row["end_time"])
    return rows


def records_on(day: date, faculty_id: int | None = None) -> list[dict]:
    """Every Attendance Record of every Class Session on `day`, whatever the session's status."""
    return _query("sub.subject_code, sub.subject_name, c.start_time, c.end_time, c.status AS session_status,"
                  " s.enrollment_no, s.name, a.status, a.minutes_late, a.method, a.confidence",
                  ["c.session_date = %s"], [day], faculty_id)


def class_session_history(student_id: int) -> list[dict]:
    """A Student's own Attendance Records, newest Class Session first."""
    return _query("c.session_date, c.start_time, c.end_time, sub.subject_code, sub.subject_name,"
                  " c.status AS session_status, a.status, a.minutes_late, a.method",
                  ["s.student_id = %s"], [student_id], None, " ORDER BY c.session_date DESC, c.start_time DESC")


def report_subjects(faculty_id: int | None = None) -> list[dict]:
    """The Subjects reports can be asked for: all of them, or a Faculty member's own and any they have held
    Class Sessions of (F6.3)."""
    where, params = "", ()
    if faculty_id is not None:
        where = (" WHERE sub.faculty_id = %s"
                 " OR EXISTS (SELECT 1 FROM class_session c WHERE c.subject_id = sub.subject_id AND c.faculty_id = %s)")
        params = (faculty_id, faculty_id)
    return db.query(
        "SELECT sub.subject_id, sub.subject_code, sub.subject_name, sub.course, sub.semester, sub.is_active"
        f" FROM subject sub{where} ORDER BY sub.is_active DESC, sub.course, sub.semester, sub.subject_code",
        params,
    )
