"""F6.1, F5.7: the five reports as Tables (faceid.reports.tables, pure).

Records are what the report queries return for closed Class Sessions: one dict per Attendance Record.
"""

from datetime import date, time

from faceid.reports.tables import date_wise, defaulters, monthly, student_wise, subject_wise

ML = {"subject_id": 1, "subject_code": "CA261481", "subject_name": "Machine Learning"}
DB = {"subject_id": 2, "subject_code": "CA261482", "subject_name": "Databases"}
ASHA = {"student_id": 1, "enrollment_no": "SSPU20260001", "name": "Asha Verma"}
RAVI = {"student_id": 2, "enrollment_no": "SSPU20260002", "name": "Ravi Kumar"}


def record(subject, student, status, minutes_late=None, session_minutes=60):
    return {**subject, **student, "status": status, "minutes_late": minutes_late, "session_minutes": session_minutes}


# ADR 0005's example: Asha is present, late by 15 of 60 minutes, absent, present: 2.75 of 4 = 68.75%.
ASHA_IN_ML = [record(ML, ASHA, "present"), record(ML, ASHA, "late", 15), record(ML, ASHA, "absent"), record(ML, ASHA, "present")]
RAVI_IN_ML = [record(ML, RAVI, "present")] * 4


def test_subject_wise_gives_each_students_counts_credit_and_percentage():
    table = subject_wise(ML, ASHA_IN_ML + RAVI_IN_ML)

    assert table.title == "Subject-wise report: CA261481 Machine Learning"
    assert table.columns == ("Enrolment Number", "Name", "Held", "Present", "Late", "Absent",
                             "Attendance Credit", "Attendance Percentage")
    assert table.rows == [
        ("SSPU20260001", "Asha Verma", 4, 2, 1, 1, 2.75, 68.8),
        ("SSPU20260002", "Ravi Kumar", 4, 4, 0, 0, 4.0, 100.0),
    ]


def test_student_wise_gives_one_row_per_subject():
    table = student_wise(ASHA, ASHA_IN_ML + [record(DB, ASHA, "absent"), record(DB, ASHA, "present")])

    assert table.title == "Student-wise report: SSPU20260001 Asha Verma"
    assert table.columns[:2] == ("Subject Code", "Subject")
    assert table.rows == [
        ("CA261481", "Machine Learning", 4, 2, 1, 1, 2.75, 68.8),
        ("CA261482", "Databases", 2, 1, 0, 1, 1.0, 50.0),
    ]


def test_the_defaulter_list_keeps_students_below_the_threshold():
    table = defaulters(ML, ASHA_IN_ML + RAVI_IN_ML, threshold=75)

    assert table.title == "Defaulter list: CA261481 Machine Learning, below 75%"
    assert [row[0] for row in table.rows] == ["SSPU20260001"]


def test_a_student_exactly_at_the_threshold_is_not_a_defaulter():
    at_75 = [record(ML, ASHA, "present")] * 3 + [record(ML, ASHA, "absent")]

    assert defaulters(ML, at_75, threshold=75).rows == []


def test_the_monthly_summary_has_a_row_per_subject_and_student():
    table = monthly(date(2026, 12, 1), RAVI_IN_ML + ASHA_IN_ML + [record(DB, ASHA, "late", 30)])

    assert table.title == "Monthly summary: December 2026"
    assert table.columns == ("Subject Code", "Subject", "Enrolment Number", "Name", "Held", "Attendance Credit",
                             "Attendance Percentage")
    assert table.rows == [
        ("CA261481", "Machine Learning", "SSPU20260001", "Asha Verma", 4, 2.75, 68.8),
        ("CA261481", "Machine Learning", "SSPU20260002", "Ravi Kumar", 4, 4.0, 100.0),
        ("CA261482", "Databases", "SSPU20260001", "Asha Verma", 1, 0.5, 50.0),
    ]


def test_the_date_wise_report_lists_every_record_with_its_session():
    row = {**ML, **ASHA, "start_time": time(10, 0), "end_time": time(11, 0), "session_status": "closed",
           "status": "late", "minutes_late": 12, "method": "face", "confidence": 0.81234}

    table = date_wise(date(2026, 12, 1), [row])

    assert table.title == "Date-wise report: 01 Dec 2026"
    assert table.columns == ("Subject Code", "Subject", "Start", "End", "Session Status", "Enrolment Number", "Name",
                             "Attendance Status", "Minutes Late", "Marking Method", "Match Confidence")
    assert table.rows == [("CA261481", "Machine Learning", "10:00", "11:00", "Closed", "SSPU20260001", "Asha Verma",
                           "Late", 12, "face", 0.81)]


def test_reports_say_which_sessions_they_count():
    assert "closed Class Sessions" in subject_wise(ML, []).note
