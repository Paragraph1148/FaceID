"""Reports (SPEC F6).

`build(kind, args, viewer)` checks what the viewer may see (F6.3), reads the records and returns one
Table; `render.render(table, fmt)` writes that Table as xlsx, PDF or CSV. `tables` holds the rules.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from faceid.reports import tables
from faceid.reports.tables import Table
from faceid.store import people, queries, teaching

KINDS = {
    "subject": "Subject-wise report",
    "student": "Student-wise report",
    "date": "Date-wise report",
    "monthly": "Monthly summary",
    "defaulters": "Defaulter list",
}


class BadReportRequest(ValueError):
    """The report can't be built as asked; the message says what to change."""


@dataclass(frozen=True)
class Viewer:
    role: str        # "admin", "faculty" or "student"
    account_id: int


def _faculty_scope(viewer: Viewer) -> int | None:
    """F6.3: a Faculty member's reports cover the Class Sessions they held; the Admin's cover everything."""
    return viewer.account_id if viewer.role == "faculty" else None


def build(kind: str, args: Mapping[str, str], viewer: Viewer, default_threshold: float) -> Table:
    """The report `kind` for `args` (the request's query string), as far as `viewer` may see it (F6.3)."""
    if kind not in KINDS or (viewer.role == "student" and kind != "student"):
        raise BadReportRequest("There is no such report.")
    scope = _faculty_scope(viewer)
    if kind == "student":
        # A Student only ever gets their own report, whatever the request says.
        student_id = viewer.account_id if viewer.role == "student" else _id(args, "student_id", "Choose a Student.")
        student = people.get_student(student_id)
        if student is None:
            raise BadReportRequest("Choose a Student.")
        return tables.student_wise(student, queries.closed_records(student_id=student_id, faculty_id=scope))
    if kind == "date":
        day = _parse(args, "date", "%Y-%m-%d", "Choose a date.").date()
        return tables.date_wise(day, queries.records_on(day, faculty_id=scope))
    if kind == "monthly":
        month = _parse(args, "month", "%Y-%m", "Choose a month.").date()
        return tables.monthly(month, queries.closed_records(month=month, faculty_id=scope))
    subject = _subject(args, scope)
    records = queries.closed_records(subject_id=subject["subject_id"], faculty_id=scope)
    if kind == "subject":
        return tables.subject_wise(subject, records)
    return tables.defaulters(subject, records, _threshold(args, default_threshold))


def form_choices(viewer: Viewer) -> dict[str, list[dict]]:
    """The Subjects and Students the report forms offer `viewer`."""
    return {"subjects": queries.report_subjects(_faculty_scope(viewer)), "students": people.list_students()}


def class_session_history(viewer: Viewer) -> list[dict]:
    """The Student's own Attendance Records, for their dashboard (F6.3)."""
    if viewer.role != "student":
        raise BadReportRequest("Only a Student has a Class Session history.")
    return queries.class_session_history(viewer.account_id)


def _id(args: Mapping[str, str], name: str, problem: str) -> int:
    """A record id from the query string, e.g. subject_id=3."""
    value = str(args.get(name, "")).strip()
    if not value.isdigit():
        raise BadReportRequest(problem)
    return int(value)


def _parse(args: Mapping[str, str], name: str, pattern: str, problem: str) -> datetime:
    try:
        return datetime.strptime(str(args.get(name, "")).strip(), pattern)
    except ValueError:
        raise BadReportRequest(problem) from None


def _subject(args: Mapping[str, str], faculty_id: int | None) -> dict:
    subject_id = _id(args, "subject_id", "Choose a Subject.")
    allowed = {s["subject_id"] for s in queries.report_subjects(faculty_id)}
    if subject_id not in allowed:
        raise BadReportRequest("Choose one of your Subjects." if faculty_id is not None else "Choose a Subject.")
    return teaching.get_subject(subject_id)


def _threshold(args: Mapping[str, str], default: float) -> float:
    text = str(args.get("threshold", "")).strip()
    if not text:
        return default
    problem = BadReportRequest("Enter a Defaulter Threshold from 1 to 100.")
    try:
        threshold = float(text)
    except ValueError:
        raise problem from None
    if not 1 <= threshold <= 100:
        raise problem
    return threshold
