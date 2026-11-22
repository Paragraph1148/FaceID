"""F1.*: three roles, bcrypt passwords, forced first-login password change, role checks, CSRF."""

from conftest import create_admin, login, submit

from faceid.store import people


def add_student(app, enrollment_no="SSPU20260001"):
    with app.app_context():
        return people.create_student(
            enrollment_no=enrollment_no, name="Asha Verma", email=None, mobile=None,
            course="MCA", semester=1, section=None,
        )


def add_faculty(app, email="teacher@college.test", password="temp-pass-1"):
    with app.app_context():
        return people.create_faculty(name="R. Sharma", email=email, department="CA", temporary_password=password)


def test_admin_created_from_the_command_line_can_log_in(app, client):
    email, password = create_admin(app)

    page = login(client, email, password)

    assert page.status_code == 200
    assert "Admin dashboard" in page.get_data(as_text=True)


def test_wrong_password_is_rejected(app, client):
    email, _ = create_admin(app)

    page = login(client, email, "not-the-password")

    assert "Wrong login or password" in page.get_data(as_text=True)
    assert client.get("/admin/").status_code == 302  # still logged out


def test_create_admin_refuses_a_short_password(app):
    result = app.test_cli_runner().invoke(args=["create-admin"], input="admin\na@b.test\nshort\nshort\n")

    assert result.exit_code != 0
    assert "at least 8" in result.output


def test_student_logs_in_with_enrolment_number_and_must_change_password_first(app, client):
    add_student(app)

    page = login(client, "SSPU20260001", "SSPU20260001")
    assert "Choose a new password" in page.get_data(as_text=True)
    assert client.get("/student/").headers["Location"].endswith("/password")

    page = submit(client, "/password", {"current_password": "SSPU20260001", "new_password": "my-new-pass", "confirm_password": "my-new-pass"})
    assert "Student dashboard" in page.get_data(as_text=True)

    client.get("/logout")
    assert "Wrong login or password" in login(client, "SSPU20260001", "SSPU20260001").get_data(as_text=True)
    assert "Student dashboard" in login(client, "SSPU20260001", "my-new-pass").get_data(as_text=True)


def test_new_password_must_differ_from_the_temporary_one(app, client):
    add_student(app)
    login(client, "SSPU20260001", "SSPU20260001")

    page = submit(client, "/password", {"current_password": "SSPU20260001", "new_password": "SSPU20260001", "confirm_password": "SSPU20260001"})

    assert "must be different" in page.get_data(as_text=True)


def test_faculty_logs_in_with_email(app, client):
    add_faculty(app)
    login(client, "teacher@college.test", "temp-pass-1")

    page = submit(client, "/password", {"current_password": "temp-pass-1", "new_password": "faculty-pass", "confirm_password": "faculty-pass"})

    assert "<h1 class=\"h3 mb-0\">Class Sessions</h1>" in page.get_data(as_text=True)


def test_each_role_is_kept_out_of_the_others_pages(app, client):
    add_student(app)
    login(client, "SSPU20260001", "SSPU20260001")
    submit(client, "/password", {"current_password": "SSPU20260001", "new_password": "my-new-pass", "confirm_password": "my-new-pass"})

    assert client.get("/admin/").status_code == 403
    assert client.get("/faculty/").status_code == 403


def test_anonymous_visitors_are_sent_to_login(client):
    response = client.get("/admin/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_forms_without_a_csrf_token_are_rejected(app, client):
    email, password = create_admin(app)

    response = client.post("/login", data={"identifier": email, "password": password})

    assert response.status_code == 400
