"""Regression tests for bugs found in the v0.2.0 review."""

import time

import numpy as np
from conftest import create_admin, csrf_token, login, submit
from fakes import encoding, face, near
from test_enrolment_pages import RAVI, capture, enrol, post, students_page
from test_registration import STUDENT

from faceid.feed import CameraFeed

ASHA_FACE, RAVI_FACE = encoding(2), encoding(1)


class CountingCamera:
    """Each opening returns frames filled with the number of times the camera has been opened."""

    opened = 0

    def __init__(self):
        CountingCamera.opened += 1
        self.value = CountingCamera.opened

    def read(self):
        time.sleep(0.005)
        return np.full((4, 4, 3), self.value, dtype=np.uint8)

    def close(self):
        pass


def test_after_going_idle_the_feed_never_returns_a_frame_from_before():
    CountingCamera.opened = 0
    feed = CameraFeed(CountingCamera, idle_seconds=0.2)
    assert feed.latest_frame()[0, 0, 0] == 1

    time.sleep(0.4)  # camera released

    assert feed.latest_frame()[0, 0, 0] == 2  # reopened, not the stale frame
    feed.stop()


def test_two_admins_enrolling_the_same_student_keep_separate_captures(app, admin_client, engine):
    submit(admin_client, "/admin/students/new", STUDENT)
    second = app.test_client()
    create_admin(app, email="second@college.test", username="second")
    login(second, "second@college.test", "admin-pass-1")

    engine.show(face(encoding=ASHA_FACE))
    capture(admin_client, 1, "front")

    assert "0 of 5 captured" in second.get("/admin/students/1/enrol").get_data(as_text=True)
    post(second, "/admin/students/1/enrol/cancel")
    assert "1 of 5 captured" in admin_client.get("/admin/students/1/enrol").get_data(as_text=True)


def test_saving_is_refused_if_another_student_was_saved_with_the_same_face_meanwhile(admin_client, engine):
    submit(admin_client, "/admin/students/new", STUDENT)
    submit(admin_client, "/admin/students/new", RAVI)
    for pose in ("front", "left", "right", "up", "down"):  # Asha's draft, captured while Ravi is not yet enrolled
        engine.show(face(encoding=near(RAVI_FACE, 0.1)))
        capture(admin_client, 1, pose)
    enrol(admin_client, engine, 2, RAVI_FACE)  # Ravi saved with the same face

    page = post(admin_client, "/admin/students/1/enrol/save").get_data(as_text=True)

    assert "matches Ravi Kumar (SSPU20260002), who is already enrolled" in page
    assert students_page(admin_client).count("Not enrolled") == 1


def test_inactive_students_cannot_be_enrolled(admin_client):
    submit(admin_client, "/admin/students/new", STUDENT)
    admin_client.post("/admin/students/1/deactivate", data={"csrf_token": csrf_token(admin_client, "/admin/")})

    page = admin_client.get("/admin/students/1/enrol", follow_redirects=True).get_data(as_text=True)

    assert "Reactivate Asha Verma before enrolling" in page


def test_a_deactivated_students_face_does_not_block_another_student(admin_client, engine):
    submit(admin_client, "/admin/students/new", RAVI)
    enrol(admin_client, engine, 1, RAVI_FACE)
    admin_client.post("/admin/students/1/deactivate", data={"csrf_token": csrf_token(admin_client, "/admin/")})
    submit(admin_client, "/admin/students/new", STUDENT)

    engine.show(face(encoding=near(RAVI_FACE, 0.3)))

    assert "Captured" in capture(admin_client, 2, "front").get_data(as_text=True)
