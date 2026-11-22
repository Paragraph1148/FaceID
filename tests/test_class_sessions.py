"""F4, F5: a Faculty member runs a Class Session, the camera marks Students, and the Faculty closes,
cancels or corrects it.

These run the real recognition thread against the scripted engine and a still camera, so the
Student "in front of the camera" is whatever face the test shows.
"""

import time

import pytest
from conftest import create_admin, csrf_token, login, submit, wait_until
from fakes import CLOSED_EYE, encoding, face, near
from test_enrolment_pages import enrol

from faceid.store import people, teaching

ASHA_FACE, RAVI_FACE = encoding(2), encoding(1)
SHARMA = ("sharma@college.test", "sharma-pass")


def add_student(enrollment_no, name, course="MCA", semester=1):
    return people.create_student(enrollment_no, name, None, None, course, semester, None)


@pytest.fixture
def classroom(app):
    """MCA semester 1: Asha (not enrolled) and Ravi (enrolled). Neha is BCA, Vikram is inactive. Sharma teaches ML."""
    with app.app_context():
        sharma = people.create_faculty("R. Sharma", SHARMA[0], "CA", "temp-pass-1")
        people.set_password("faculty", sharma, SHARMA[1])
        other = people.create_faculty("P. Iyer", "iyer@college.test", "CA", "temp-pass-1")
        people.set_password("faculty", other, "iyer-pass-1")
        ids = {
            "ml": teaching.create_subject("CA261481", "Machine Learning", "MCA", 1, sharma),
            "dbms": teaching.create_subject("CA261482", "Databases", "MCA", 1, other),
            "empty": teaching.create_subject("CA269999", "Seminar", "MCA", 4, sharma),
            "asha": add_student("SSPU20260001", "Asha Verma"),
            "ravi": add_student("SSPU20260002", "Ravi Kumar"),
            "neha": add_student("SSPU20260003", "Neha Joshi", course="BCA"),
            "vikram": add_student("SSPU20260004", "Vikram Rao"),
        }
        people.set_active("student", ids["vikram"], False)
        people.replace_encodings(ids["ravi"], [RAVI_FACE])
    return ids


@pytest.fixture
def faculty_client(app, client, classroom):
    login(client, *SHARMA)
    return client


def start(client, subject_id, start_time="10:00", end_time="11:00", room_no="204"):
    return submit(client, "/faculty/sessions/new",
                  {"subject_id": subject_id, "start_time": start_time, "end_time": end_time, "room_no": room_no})


def status(client, session_id=1):
    return client.get(f"/faculty/sessions/{session_id}/status").get_json()


def post(client, url, data=None):
    return client.post(url, data={**(data or {}), "csrf_token": csrf_token(client, "/faculty/")}, follow_redirects=True)


def blink(engine, encoding_):
    """Show a face, close its eyes, open them again: long enough for the recognition thread to see each step."""
    engine.show(face(encoding=encoding_))
    time.sleep(0.15)
    engine.show(face(encoding=encoding_, eyes=CLOSED_EYE))
    time.sleep(0.15)
    engine.show(face(encoding=encoding_))


def test_starting_a_class_session_opens_it_with_an_absent_record_per_expected_student(faculty_client, classroom):
    page = start(faculty_client, classroom["ml"]).get_data(as_text=True)

    assert "Machine Learning" in page and "Open" in page
    now = status(faculty_client)
    assert (now["status"], now["attended"], now["expected"], now["recognising"], now["error"]) == ("open", 0, 2, True, None)
    # Neha is in another Programme and Vikram is inactive, so neither is expected.
    assert "Asha Verma" in page and "Ravi Kumar" in page
    assert "Neha Joshi" not in page and "Vikram Rao" not in page


def test_the_page_warns_about_expected_students_who_are_not_enrolled(faculty_client, classroom):
    page = start(faculty_client, classroom["ml"]).get_data(as_text=True)

    assert "1 Expected Student not enrolled" in page and "Asha Verma. Use Manual Override" in page


def test_a_student_who_matches_and_blinks_is_marked_present_with_confidence(faculty_client, classroom, engine):
    start(faculty_client, classroom["ml"])

    blink(engine, near(RAVI_FACE, 0.2))

    wait_until(lambda: status(faculty_client)["attended"] == 1)
    assert status(faculty_client)["marked"] == [{"name": "Ravi Kumar", "status": "present", "minutes_late": None}]
    page = faculty_client.get("/faculty/sessions/1").get_data(as_text=True)
    assert "<td>Present</td>" in page and "<td>0.80</td>" in page and "<td>face</td>" in page


def test_a_student_who_never_blinks_is_not_marked(faculty_client, classroom, engine, app):
    start(faculty_client, classroom["ml"])

    engine.show(face(encoding=RAVI_FACE))
    wait_until(lambda: [f.state for f in app.extensions["live"].faces] == ["waiting"])

    assert status(faculty_client)["attended"] == 0


def test_a_student_recognised_after_the_late_threshold_is_late_by_whole_minutes(faculty_client, classroom, engine, clock):
    start(faculty_client, classroom["ml"], start_time="09:35")  # the clock says 10:00

    blink(engine, RAVI_FACE)

    wait_until(lambda: status(faculty_client)["attended"] == 1)
    assert status(faculty_client)["marked"] == [{"name": "Ravi Kumar", "status": "late", "minutes_late": 25}]


def test_only_one_class_session_can_be_open_at_a_time(app, faculty_client, classroom):
    start(faculty_client, classroom["ml"])
    iyer = app.test_client()
    login(iyer, "iyer@college.test", "iyer-pass-1")

    page = start(iyer, classroom["dbms"]).get_data(as_text=True)

    assert "R. Sharma&#39;s CA261481 Class Session is still open." in page
    assert "R. Sharma's CA261481 Class Session is open." in iyer.get("/faculty/").get_data(as_text=True)


def test_a_subject_with_no_expected_students_cannot_be_started(faculty_client, classroom):
    page = start(faculty_client, classroom["empty"]).get_data(as_text=True)

    assert "No active Students are registered in MCA semester 4." in page


def test_a_faculty_member_can_only_start_sessions_for_their_own_subjects(faculty_client, classroom):
    page = start(faculty_client, classroom["dbms"]).get_data(as_text=True)

    assert "Choose one of your Subjects." in page


def test_another_faculty_members_session_is_not_found(app, faculty_client, classroom):
    start(faculty_client, classroom["ml"])
    iyer = app.test_client()
    login(iyer, "iyer@college.test", "iyer-pass-1")

    assert iyer.get("/faculty/sessions/1").status_code == 404
    assert iyer.get("/faculty/sessions/1/status").status_code == 404


def test_closing_stops_recognition_and_leaves_unmarked_students_absent(app, faculty_client, classroom, engine):
    start(faculty_client, classroom["ml"])

    page = post(faculty_client, "/faculty/sessions/1/close").get_data(as_text=True)
    blink(engine, RAVI_FACE)

    assert "Class Session closed. Students not marked are absent." in page
    assert app.extensions["live"].session_id is None
    assert status(faculty_client)["status"] == "closed" and status(faculty_client)["attended"] == 0
    assert faculty_client.get("/faculty/sessions/1/stream").status_code == 404
    # The camera is free for the next Class Session.
    assert "Machine Learning" in start(faculty_client, classroom["ml"]).get_data(as_text=True)


def test_cancelling_a_session_stops_recognition_and_freezes_its_records(app, faculty_client, classroom):
    start(faculty_client, classroom["ml"])

    page = post(faculty_client, "/faculty/sessions/1/cancel").get_data(as_text=True)
    refused = post(faculty_client, f"/faculty/sessions/1/records/{classroom['asha']}", {"status": "present"})

    assert "Class Session cancelled." in page
    assert app.extensions["live"].session_id is None
    assert status(faculty_client)["status"] == "cancelled"
    assert "can&#39;t be changed" in refused.get_data(as_text=True)


def test_manual_override_sets_late_with_minutes(faculty_client, classroom):
    start(faculty_client, classroom["ml"])

    page = post(faculty_client, f"/faculty/sessions/1/records/{classroom['asha']}", {"status": "late", "minutes_late": "15"})

    text = page.get_data(as_text=True)
    assert "Attendance Record updated by Manual Override." in text
    assert "<td>Late (15 min)</td>" in text and "<td>manual</td>" in text
    assert status(faculty_client)["attended"] == 1


def test_manual_override_to_late_needs_the_minutes(faculty_client, classroom):
    start(faculty_client, classroom["ml"])

    page = post(faculty_client, f"/faculty/sessions/1/records/{classroom['asha']}", {"status": "late"})

    assert "Enter how many minutes late, from 1 to 60." in page.get_data(as_text=True)


def test_manual_override_works_on_a_closed_session(faculty_client, classroom):
    start(faculty_client, classroom["ml"])
    post(faculty_client, "/faculty/sessions/1/close")

    post(faculty_client, f"/faculty/sessions/1/records/{classroom['asha']}", {"status": "present"})

    assert status(faculty_client)["attended"] == 1


def test_overriding_a_student_who_is_not_expected_is_not_found(faculty_client, classroom):
    start(faculty_client, classroom["ml"])

    response = faculty_client.post(f"/faculty/sessions/1/records/{classroom['neha']}",
                                   data={"status": "present", "csrf_token": csrf_token(faculty_client, "/faculty/")})

    assert response.status_code == 404


def test_the_camera_never_undoes_a_manual_override(app, faculty_client, classroom, engine):
    start(faculty_client, classroom["ml"])
    post(faculty_client, f"/faculty/sessions/1/records/{classroom['ravi']}", {"status": "absent"})
    faculty_client.get("/faculty/sessions/1")

    blink(engine, RAVI_FACE)
    wait_until(lambda: [f.state for f in app.extensions["live"].faces] == ["marked"])

    page = faculty_client.get("/faculty/sessions/1").get_data(as_text=True)
    assert status(faculty_client)["attended"] == 0 and "<td>manual</td>" in page


def test_a_student_enrolled_during_the_session_is_recognised(app, faculty_client, classroom, engine):
    start(faculty_client, classroom["ml"])
    admin = app.test_client()
    login(admin, *create_admin(app))
    enrol(admin, engine, classroom["asha"], ASHA_FACE)

    blink(engine, ASHA_FACE)

    wait_until(lambda: status(faculty_client)["attended"] == 1)
    assert status(faculty_client)["marked"][0]["name"] == "Asha Verma"


def test_opening_the_page_resumes_recognition_after_a_restart(app, faculty_client, classroom):
    start(faculty_client, classroom["ml"])
    app.extensions["live"].stop()  # as if the server had restarted
    assert status(faculty_client)["recognising"] is False

    faculty_client.get("/faculty/sessions/1")

    assert status(faculty_client)["recognising"] is True


def test_the_start_form_offers_the_faculty_members_subjects_and_the_current_time(faculty_client):
    page = faculty_client.get("/faculty/sessions/new").get_data(as_text=True)

    assert "CA261481 Machine Learning" in page and "CA261482" not in page
    assert 'value="10:00"' in page and 'value="11:00"' in page



# --- Review fixes ---


def test_a_closed_class_session_cannot_be_cancelled(faculty_client, classroom):
    start(faculty_client, classroom["ml"])
    post(faculty_client, "/faculty/sessions/1/close")

    page = post(faculty_client, "/faculty/sessions/1/cancel").get_data(as_text=True)

    assert "Only an open Class Session can be cancelled." in page
    assert status(faculty_client)["status"] == "closed"


def test_the_same_manual_override_can_be_saved_twice(faculty_client, classroom):
    start(faculty_client, classroom["ml"])
    url = f"/faculty/sessions/1/records/{classroom['asha']}"

    post(faculty_client, url, {"status": "present"})
    page = post(faculty_client, url, {"status": "present"})

    assert "Attendance Record updated by Manual Override." in page.get_data(as_text=True)
