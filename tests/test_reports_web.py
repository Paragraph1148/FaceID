"""F6.1-F6.3 through the web: who sees which report, in the browser and as downloads; the Student's own view."""

import csv
import io
from datetime import date, datetime, time

import pytest

from conftest import create_admin, login

from faceid.store import attendance, people, teaching

SHARMA = ("sharma@college.test", "sharma-pass-1")
IYER = ("iyer@college.test", "iyer-pass-1")
DAY = date(2026, 12, 1)


def faculty(name, credentials):
    faculty_id = people.create_faculty(name, credentials[0], "CA", "temp-pass-1")
    people.set_password("faculty", faculty_id, credentials[1])
    return faculty_id


def held(faculty_id, subject_id, day, marks, status="closed"):
    """A Class Session on `day`, 10:00-11:00, with each Student's mark: {student_id: (status, minutes_late)}."""
    session_id = attendance.open_class_session(faculty_id, subject_id, day, time(10, 0), time(11, 0), None)
    for student_id, (mark, minutes) in marks.items():
        attendance.override(session_id, student_id, mark, minutes, at=datetime.combine(day, time(10, 5)))
    if status == "closed":
        attendance.close(session_id)
    elif status == "cancelled":
        attendance.cancel(session_id)
    return session_id


@pytest.fixture
def college(app):
    """Asha and Ravi in MCA semester 1. Sharma teaches ML, Iyer teaches Databases.

    ML: Asha present, late 15 of 60, absent, present (68.75%); Ravi always present. One cancelled, one open.
    Databases: Asha absent once (0%).
    """
    create_admin(app)
    with app.app_context():
        sharma, iyer = faculty("R. Sharma", SHARMA), faculty("P. Iyer", IYER)
        ml = teaching.create_subject("CA261481", "Machine Learning", "MCA", 1, sharma)
        dbms = teaching.create_subject("CA261482", "Databases", "MCA", 1, iyer)
        asha = people.create_student("SSPU20260001", "Asha Verma", None, None, "MCA", 1, None)
        ravi = people.create_student("SSPU20260002", "Ravi Kumar", None, None, "MCA", 1, None)
        people.set_password("student", asha, "asha-pass-1")
        people.set_password("student", ravi, "ravi-pass-1")
        present = ("present", None)
        for day, asha_mark in ((DAY, present), (date(2026, 12, 2), ("late", 15)),
                               (date(2026, 12, 3), ("absent", None)), (date(2026, 12, 4), present)):
            held(sharma, ml, day, {asha: asha_mark, ravi: present})
        held(sharma, ml, date(2026, 12, 5), {asha: ("absent", None)}, status="cancelled")
        held(iyer, dbms, DAY, {asha: ("absent", None), ravi: present})
        held(sharma, ml, date(2026, 12, 6), {asha: ("absent", None)}, status="open")
    return {"ml": ml, "dbms": dbms, "asha": asha, "ravi": ravi}


def page(client, url):
    response = client.get(url)
    assert response.status_code == 200, response.status_code
    return response.get_data(as_text=True)


def problem(client, url):
    """A report request that can't be built: the reports page again, saying what to change."""
    response = client.get(url)
    assert response.status_code == 400, response.status_code
    return response.get_data(as_text=True)


def csv_rows(client, url):
    response = client.get(url)
    assert response.status_code == 200 and response.mimetype == "text/csv"
    return list(csv.reader(io.StringIO(response.get_data().decode("utf-8-sig"))))[1:]


def test_the_admin_sees_a_subject_wise_report_counting_closed_sessions_only(client, college):
    login(client, "admin@college.test", "admin-pass-1")

    html = page(client, f"/reports/subject?subject_id={college['ml']}")

    assert "Subject-wise report: CA261481 Machine Learning" in html
    assert "<td>68.8</td>" in html and "<td>100.0</td>" in html
    rows = csv_rows(client, f"/reports/subject/csv?subject_id={college['ml']}")
    assert [row[:3] + row[-1:] for row in rows] == [["SSPU20260001", "Asha Verma", "4", "68.8"],
                                                    ["SSPU20260002", "Ravi Kumar", "4", "100.0"]]


@pytest.mark.parametrize("fmt, mimetype", [("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                                           ("pdf", "application/pdf")])
def test_every_report_downloads_as_xlsx_and_pdf_too(client, college, fmt, mimetype):
    login(client, "admin@college.test", "admin-pass-1")

    response = client.get(f"/reports/defaulters/{fmt}?subject_id={college['ml']}")

    assert response.status_code == 200 and response.mimetype == mimetype
    assert 'filename="defaulters-' in response.headers["Content-Disposition"]


def test_the_defaulter_list_uses_the_default_threshold_or_the_one_asked_for(client, college):
    login(client, "admin@college.test", "admin-pass-1")

    assert [row[0] for row in csv_rows(client, f"/reports/defaulters/csv?subject_id={college['ml']}")] == ["SSPU20260001"]
    assert csv_rows(client, f"/reports/defaulters/csv?subject_id={college['ml']}&threshold=60") == []


def test_student_wise_monthly_and_date_wise_reports(client, college):
    login(client, "admin@college.test", "admin-pass-1")

    student = csv_rows(client, f"/reports/student/csv?student_id={college['asha']}")
    monthly = csv_rows(client, "/reports/monthly/csv?month=2026-12")
    day = csv_rows(client, "/reports/date/csv?date=2026-12-01")

    assert [(row[0], row[-1]) for row in student] == [("CA261481", "68.8"), ("CA261482", "0.0")]
    assert len(monthly) == 4  # 2 Subjects x 2 Students
    assert [(row[0], row[5], row[7]) for row in day] == [("CA261481", "SSPU20260001", "Present"),
                                                        ("CA261481", "SSPU20260002", "Present"),
                                                        ("CA261482", "SSPU20260001", "Absent"),
                                                        ("CA261482", "SSPU20260002", "Present")]


def test_a_faculty_member_sees_only_their_own_subjects(client, college):
    login(client, *SHARMA)

    assert "Choose one of your Subjects." in problem(client, f"/reports/subject?subject_id={college['dbms']}")
    assert [row[0] for row in csv_rows(client, f"/reports/student/csv?student_id={college['asha']}")] == ["CA261481"]
    assert {row[0] for row in csv_rows(client, "/reports/date/csv?date=2026-12-01")} == {"CA261481"}
    index = page(client, "/reports/")
    assert "Machine Learning" in index and "Databases" not in index


def test_a_bad_request_says_what_to_change(client, college):
    login(client, "admin@college.test", "admin-pass-1")

    assert "Choose a month." in problem(client, "/reports/monthly?month=december")
    assert "Enter a Defaulter Threshold from 1 to 100." in problem(client, f"/reports/defaulters?subject_id={college['ml']}&threshold=500")
    assert client.get("/reports/subject/docx?subject_id=1").status_code == 404


def test_students_cannot_open_the_report_pages(client, college):
    login(client, "SSPU20260001", "asha-pass-1")

    assert client.get("/reports/").status_code == 403
    assert client.get(f"/reports/subject/csv?subject_id={college['ml']}").status_code == 403


def test_a_student_sees_their_own_report_and_session_history(client, college):
    login(client, "SSPU20260001", "asha-pass-1")

    html = page(client, "/student/")

    assert "Student-wise report: SSPU20260001 Asha Verma" in html and "<td>68.8</td>" in html
    assert "Ravi Kumar" not in html
    # History: every record, newest first, including the open and cancelled sessions with their status.
    assert html.index("06 Dec 2026") < html.index("05 Dec 2026") < html.index("01 Dec 2026")
    assert "Cancelled" in html and "Open" in html
    assert [row[0] for row in csv_rows(client, "/student/report/csv")] == ["CA261481", "CA261482"]
    assert client.get("/student/report/csv?student_id=%d" % college["ravi"]).status_code == 200
    assert "Ravi Kumar" not in client.get("/student/report/csv?student_id=%d" % college["ravi"]).get_data(as_text=True)
