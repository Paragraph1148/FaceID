"""Attendance Records: opening a Class Session, marking, Manual Override, closing and cancelling (SPEC F5)."""

import threading
from datetime import date, datetime, time

from faceid.store import db

# One process serves the app (ADR 0004), so this lock is enough to stop two Faculty opening sessions at once.
_opening = threading.Lock()


class CannotOpen(Exception):
    """The Class Session can't be opened; the message says why."""


def open_class_session(
    faculty_id: int, subject_id: int, session_date: date, start_time: time, end_time: time, room_no: str | None
) -> int:
    """Create and open a Class Session with an absent record per Expected Student (F5.2, ADR 0007)."""
    with _opening:
        other = db.query_one(
            "SELECT s.subject_code, f.name FROM class_session c JOIN subject s ON s.subject_id = c.subject_id"
            " JOIN faculty f ON f.faculty_id = c.faculty_id WHERE c.status = 'open' LIMIT 1"
        )
        if other:
            raise CannotOpen(
                f"{other['name']}'s {other['subject_code']} Class Session is still open. The camera serves one session at a time."
            )
        subject = db.query_one("SELECT course, semester FROM subject WHERE subject_id = %s", (subject_id,))
        expected = db.query(
            "SELECT student_id FROM student WHERE course = %s AND semester = %s AND is_active",
            (subject["course"], subject["semester"]),
        )
        if not expected:
            raise CannotOpen(f"No active Students are registered in {subject['course']} semester {subject['semester']}.")
        with db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO class_session (subject_id, faculty_id, session_date, start_time, end_time, room_no, status)"
                " VALUES (%s, %s, %s, %s, %s, %s, 'open')",
                (subject_id, faculty_id, session_date, start_time, end_time, room_no),
            )
            session_id = cursor.lastrowid
            cursor.executemany(
                "INSERT INTO attendance (session_id, student_id, status, method, marked_at) VALUES (%s, %s, 'absent', 'face', NULL)",
                [(session_id, row["student_id"]) for row in expected],
            )
        return session_id


def records(session_id: int) -> list[dict]:
    """Every Attendance Record of the session, with the Student's name and whether their face is enrolled."""
    return db.query(
        "SELECT a.student_id, s.enrollment_no, s.name, a.status, a.minutes_late, a.method, a.marked_at, a.confidence,"
        " EXISTS (SELECT 1 FROM face_encoding e WHERE e.student_id = a.student_id) AS enrolled"
        " FROM attendance a JOIN student s ON s.student_id = a.student_id WHERE a.session_id = %s ORDER BY s.enrollment_no",
        (session_id,),
    )


def mark_recognised(
    session_id: int, student_id: int, status: str, minutes_late: int | None, confidence: float, marked_at: datetime
) -> bool:
    """Record a recognition (F5.3). Only an absent, face-method record in an open session changes:
    the first recognition wins, and a Manual Override is never undone by the camera."""
    conn = db.connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE attendance a JOIN class_session c ON c.session_id = a.session_id"
        " SET a.status = %s, a.minutes_late = %s, a.confidence = %s, a.marked_at = %s"
        " WHERE a.session_id = %s AND a.student_id = %s AND a.status = 'absent' AND a.method = 'face' AND c.status = 'open'",
        (status, minutes_late, confidence, marked_at, session_id, student_id),
    )
    conn.commit()
    changed = cursor.rowcount == 1
    cursor.close()
    return changed


def override(session_id: int, student_id: int, status: str, minutes_late: int | None, at: datetime) -> bool:
    """Manual Override (F5.6). False if the Student has no record in this session."""
    if db.query_one("SELECT 1 AS found FROM attendance WHERE session_id = %s AND student_id = %s", (session_id, student_id)) is None:
        return False
    db.execute(
        "UPDATE attendance SET status = %s, minutes_late = %s, method = 'manual', confidence = NULL, marked_at = %s"
        " WHERE session_id = %s AND student_id = %s",
        (status, minutes_late, at, session_id, student_id),
    )
    return True


def close(session_id: int) -> None:
    """F5.4: the remaining absent records become final. Only an open session can be closed."""
    db.execute("UPDATE class_session SET status = 'closed' WHERE session_id = %s AND status = 'open'", (session_id,))


def cancel(session_id: int) -> None:
    """F5.5: the class did not happen. It counts towards nobody's Attendance Percentage."""
    db.execute("UPDATE class_session SET status = 'cancelled' WHERE session_id = %s", (session_id,))


def marked_students(session_id: int) -> set[int]:
    """Students whose record is no longer absent, or was set by hand: recognition leaves them alone."""
    rows = db.query(
        "SELECT student_id FROM attendance WHERE session_id = %s AND (status <> 'absent' OR method = 'manual')", (session_id,)
    )
    return {row["student_id"] for row in rows}
