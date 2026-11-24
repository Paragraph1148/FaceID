"""The five reports of F6.1 as Tables (pure).

Each builder takes the records the report queries return and gives back one Table. Every format is
written from that same Table, so the browser, xlsx, PDF and CSV show the same rows (F6.2).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from faceid.attendance import credit, percentage

COUNTED = "Counts closed Class Sessions only: an open one is counted once it is closed, and cancelled ones never are."
TOTALS = ("Held", "Present", "Late", "Absent", "Attendance Credit", "Attendance Percentage")


@dataclass(frozen=True)
class Table:
    title: str
    columns: tuple[str, ...]
    rows: list[tuple]
    note: str = ""


@dataclass(frozen=True)
class Standing:
    """One Student's attendance in one Subject (F5.7)."""

    held: int
    present: int
    late: int
    absent: int
    credit: float
    percentage: float

    def totals(self) -> tuple:
        return (self.held, self.present, self.late, self.absent, round(self.credit, 2), round(self.percentage, 1))


def standings(records: list[dict]) -> dict[tuple[int, int], Standing]:
    """Each (subject_id, student_id) in the records, with their Attendance Credit and Percentage."""
    grouped = defaultdict(list)
    for r in records:
        grouped[(r["subject_id"], r["student_id"])].append(r)
    result = {}
    for key, rows in grouped.items():
        credits = [credit(r["status"], r["minutes_late"], r["session_minutes"]) for r in rows]
        count = {status: sum(r["status"] == status for r in rows) for status in ("present", "late", "absent")}
        result[key] = Standing(len(rows), count["present"], count["late"], count["absent"],
                               sum(credits), percentage(credits, len(rows)))
    return result


def _people(records: list[dict]) -> dict[int, dict]:
    return {r["student_id"]: r for r in records}


def _subjects(records: list[dict]) -> dict[int, dict]:
    return {r["subject_id"]: r for r in records}


def subject_wise(subject: dict, records: list[dict]) -> Table:
    """Each Student's Attendance Percentage in one Subject."""
    people = _people(records)
    rows = [(people[student_id]["enrollment_no"], people[student_id]["name"], *standing.totals())
            for (_, student_id), standing in standings(records).items()]
    return Table(f"Subject-wise report: {_subject_name(subject)}", ("Enrolment Number", "Name", *TOTALS),
                 sorted(rows), COUNTED)


def student_wise(student: dict, records: list[dict]) -> Table:
    """One Student's Attendance Percentage in each of their Subjects."""
    subjects = _subjects(records)
    rows = [(subjects[subject_id]["subject_code"], subjects[subject_id]["subject_name"], *standing.totals())
            for (subject_id, _), standing in standings(records).items()]
    return Table(f"Student-wise report: {student['enrollment_no']} {student['name']}", ("Subject Code", "Subject", *TOTALS),
                 sorted(rows), COUNTED)


def defaulters(subject: dict, records: list[dict], threshold: float) -> Table:
    """Students below the Defaulter Threshold in one Subject."""
    report = subject_wise(subject, records)
    below = [row for row in report.rows if row[-1] < threshold]
    return Table(f"Defaulter list: {_subject_name(subject)}, below {threshold:g}%", report.columns, below, COUNTED)


def monthly(month: date, records: list[dict]) -> Table:
    """Each Subject x Student, for the Class Sessions of one calendar month."""
    subjects, people = _subjects(records), _people(records)
    rows = []
    for (subject_id, student_id), standing in standings(records).items():
        subject, person = subjects[subject_id], people[student_id]
        rows.append((subject["subject_code"], subject["subject_name"], person["enrollment_no"], person["name"],
                     standing.held, round(standing.credit, 2), round(standing.percentage, 1)))
    columns = ("Subject Code", "Subject", "Enrolment Number", "Name", "Held", "Attendance Credit", "Attendance Percentage")
    return Table(f"Monthly summary: {month:%B %Y}", columns, sorted(rows), COUNTED)


def date_wise(day: date, records: list[dict]) -> Table:
    """Every record of every Class Session on one date, whatever the session's status."""
    rows = [(r["subject_code"], r["subject_name"], f"{r['start_time']:%H:%M}", f"{r['end_time']:%H:%M}",
             r["session_status"].capitalize(), r["enrollment_no"], r["name"], r["status"].capitalize(),
             r["minutes_late"], r["method"], None if r["confidence"] is None else round(r["confidence"], 2))
            for r in records]
    columns = ("Subject Code", "Subject", "Start", "End", "Session Status", "Enrolment Number", "Name",
               "Attendance Status", "Minutes Late", "Marking Method", "Match Confidence")
    return Table(f"Date-wise report: {day:%d %b %Y}", columns, sorted(rows, key=lambda row: (row[2], row[0], row[5])))


def _subject_name(subject: dict) -> str:
    return f"{subject['subject_code']} {subject['subject_name']}"
