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


def build(kind: str, args: Mapping[str, str], viewer: Viewer, default_threshold: float) -> Table:
    """The report `kind` for `args` (the request's query string), as far as `viewer` may see it (F6.3)."""
    if kind not in KINDS or (viewer.role == "student" and kind != "student"):
        raise BadReportRequest("There is no such report.")
    scope = viewer.account_id if viewer.role == "faculty" else None  # Faculty see their own Subjects only
    if kind == "student":
        student_id = viewer.account_id if viewer.role == "student" else _number(args, "student_id", "Choose a Student.")
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
    records = queries.closed_records(subject_id=subject["subject_id"])
    if kind == "subject":
        return tables.subject_wise(subject, records)
    return tables.defaulters(subject, records, _threshold(args, default_threshold))


def _number(args: Mapping[str, str], name: str, problem: str) -> int:
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
    subject = teaching.get_subject(_number(args, "subject_id", "Choose a Subject."))
    if subject is None or (faculty_id is not None and subject["faculty_id"] != faculty_id):
        raise BadReportRequest("Choose one of your Subjects." if faculty_id is not None else "Choose a Subject.")
    return subject


def _threshold(args: Mapping[str, str], default: float) -> float:
    text = str(args.get("threshold", "")).strip()
    if not text:
        return default
    try:
        threshold = float(text)
    except ValueError:
        threshold = -1
    if not 1 <= threshold <= 100:
        raise BadReportRequest("Enter a Defaulter Threshold from 1 to 100.")
    return threshold
