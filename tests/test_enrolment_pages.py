"""F3.1, F3.3, F3.4: the Admin enrols a Student's face from five guided Captures."""

from conftest import csrf_token, submit
from fakes import encoding, face, near
from test_registration import STUDENT

from faceid.enrolment import POSES

RAVI = {**STUDENT, "enrollment_no": "SSPU20260002", "name": "Ravi Kumar", "email": "ravi@college.test"}
ASHA_FACE = encoding(2)
RAVI_FACE = encoding(1)


def post(client, url):
    return client.post(url, data={"csrf_token": csrf_token(client, "/admin/")}, follow_redirects=True)


def capture(client, student_id, pose):
    return client.post(
        f"/admin/students/{student_id}/enrol/capture",
        data={"pose": pose, "csrf_token": csrf_token(client, "/admin/")},
        follow_redirects=True,
    )


def enrol(client, engine, student_id, base):
    for index, pose in enumerate(POSES):
        engine.show(face(encoding=near(base, 0.05 * (index + 1))))
        capture(client, student_id, pose)
    return post(client, f"/admin/students/{student_id}/enrol/save")


def students_page(client):
    return client.get("/admin/students/").get_data(as_text=True)


def test_admin_enrols_a_student_from_five_poses(admin_client, engine):
    submit(admin_client, "/admin/students/new", STUDENT)
    assert "Not enrolled" in students_page(admin_client)

    page = enrol(admin_client, engine, 1, ASHA_FACE)

    assert "Face Enrolment saved for Asha Verma" in page.get_data(as_text=True)
    assert "Enrolled (5)" in students_page(admin_client)


def test_each_capture_shows_whether_it_was_accepted(admin_client, engine):
    submit(admin_client, "/admin/students/new", STUDENT)

    engine.show(face(encoding=ASHA_FACE))
    accepted = capture(admin_client, 1, "front").get_data(as_text=True)
    engine.show()
    rejected = capture(admin_client, 1, "left").get_data(as_text=True)

    assert "Captured: Look straight at the camera" in accepted
    assert "No face found" in rejected
    assert "1 of 5 captured" in rejected


def test_saving_before_all_five_poses_are_captured_is_refused(admin_client, engine):
    submit(admin_client, "/admin/students/new", STUDENT)
    engine.show(face(encoding=ASHA_FACE))
    capture(admin_client, 1, "front")

    page = post(admin_client, "/admin/students/1/enrol/save").get_data(as_text=True)

    assert "Capture all 5 poses first" in page
    assert "Not enrolled" in students_page(admin_client)


def test_a_face_already_enrolled_for_another_student_is_refused(admin_client, engine):
    submit(admin_client, "/admin/students/new", RAVI)
    enrol(admin_client, engine, 1, RAVI_FACE)
    submit(admin_client, "/admin/students/new", STUDENT)

    engine.show(face(encoding=near(RAVI_FACE, 0.3)))
    page = capture(admin_client, 2, "front").get_data(as_text=True)

    assert "matches Ravi Kumar (SSPU20260002), who is already enrolled" in page


def test_re_enrolling_replaces_the_previous_encodings(admin_client, engine):
    submit(admin_client, "/admin/students/new", RAVI)
    enrol(admin_client, engine, 1, RAVI_FACE)
    enrol(admin_client, engine, 1, encoding(7))  # Ravi re-enrolled with a different face
    submit(admin_client, "/admin/students/new", STUDENT)

    engine.show(face(encoding=near(RAVI_FACE, 0.3)))  # close to Ravi's *old* encodings only
    page = capture(admin_client, 2, "front").get_data(as_text=True)

    assert "Captured" in page
    assert "Enrolled (5)" in students_page(admin_client)


def test_re_enrolling_a_student_does_not_clash_with_their_own_old_face(admin_client, engine):
    submit(admin_client, "/admin/students/new", STUDENT)
    enrol(admin_client, engine, 1, ASHA_FACE)

    page = enrol(admin_client, engine, 1, ASHA_FACE)

    assert "Face Enrolment saved" in page.get_data(as_text=True)


def test_cancelling_discards_the_captures(admin_client, engine):
    submit(admin_client, "/admin/students/new", STUDENT)
    engine.show(face(encoding=ASHA_FACE))
    capture(admin_client, 1, "front")

    post(admin_client, "/admin/students/1/enrol/cancel")

    assert "0 of 5 captured" in admin_client.get("/admin/students/1/enrol").get_data(as_text=True)
    assert "Not enrolled" in students_page(admin_client)


def test_enrolment_page_shows_every_pose_instruction(admin_client):
    submit(admin_client, "/admin/students/new", STUDENT)

    html = admin_client.get("/admin/students/1/enrol").get_data(as_text=True)

    assert all(instruction in html for instruction in POSES.values())
