"""F2.*: the Admin registers Students, Faculty and Subjects; records are deactivated, never deleted."""

from conftest import login, submit

STUDENT = {
    "enrollment_no": "SSPU20260001", "name": "Asha Verma", "email": "asha@college.test", "mobile": "",
    "course": "MCA", "semester": "1", "section": "A",
}
FACULTY = {"name": "R. Sharma", "email": "sharma@college.test", "department": "CA", "temporary_password": "temp-pass-1"}


def add_faculty(admin_client, **overrides):
    return submit(admin_client, "/admin/faculty/new", {**FACULTY, **overrides})


def faculty_id_named(admin_client, name):
    import re

    html = admin_client.get("/admin/faculty/").get_data(as_text=True)
    return re.search(rf'href="/admin/faculty/(\d+)/edit">{re.escape(name)}<', html).group(1)


def subject_form(admin_client, **overrides):
    add_faculty(admin_client)
    form = {
        "subject_code": "CA261481", "subject_name": "Machine Learning", "course": "MCA", "semester": "1",
        "faculty_id": faculty_id_named(admin_client, "R. Sharma"),
    }
    return {**form, **overrides}


# --- Students ---


def test_admin_adds_a_student_who_can_then_log_in(admin_client, app):
    page = submit(admin_client, "/admin/students/new", STUDENT)

    assert "Asha Verma" in page.get_data(as_text=True)
    student = app.test_client()
    assert "Choose a new password" in login(student, "SSPU20260001", "SSPU20260001").get_data(as_text=True)


def test_duplicate_enrolment_number_is_refused_with_the_reason(admin_client):
    submit(admin_client, "/admin/students/new", STUDENT)

    page = submit(admin_client, "/admin/students/new", {**STUDENT, "email": "other@college.test"})

    assert "already used by another Student" in page.get_data(as_text=True)
    assert admin_client.get("/admin/students/").get_data(as_text=True).count("SSPU20260001") == 1


def test_student_fields_are_validated(admin_client):
    page = submit(admin_client, "/admin/students/new", {**STUDENT, "semester": "13", "name": "  ", "mobile": "12ab"})
    html = page.get_data(as_text=True)

    assert "Semester must be a number from 1 to 12" in html
    assert "Name is required" in html
    assert "Mobile must be digits" in html
    assert "SSPU20260001" not in admin_client.get("/admin/students/").get_data(as_text=True)


def test_admin_edits_a_student(admin_client):
    submit(admin_client, "/admin/students/new", STUDENT)

    page = submit(admin_client, "/admin/students/1/edit", {**STUDENT, "name": "Asha V. Verma", "semester": "2"})

    assert "Asha V. Verma" in page.get_data(as_text=True)


def test_deactivated_student_cannot_log_in_but_stays_listed(admin_client, app):
    submit(admin_client, "/admin/students/new", STUDENT)

    page = admin_client.post(
        "/admin/students/1/deactivate",
        data={"csrf_token": _token(admin_client, "/admin/students/")},
        follow_redirects=True,
    )

    html = page.get_data(as_text=True)
    assert "Asha Verma" in html and "Inactive" in html
    assert "Wrong login or password" in login(app.test_client(), "SSPU20260001", "SSPU20260001").get_data(as_text=True)


def _token(client, url):
    from conftest import csrf_token

    return csrf_token(client, url)


# --- Faculty ---


def test_admin_adds_faculty_who_must_change_the_temporary_password(admin_client, app):
    add_faculty(admin_client)

    page = login(app.test_client(), "sharma@college.test", "temp-pass-1")

    assert "Choose a new password" in page.get_data(as_text=True)


def test_duplicate_faculty_email_is_refused(admin_client):
    add_faculty(admin_client)

    page = add_faculty(admin_client, name="Someone Else")

    assert "already used by another account" in page.get_data(as_text=True)


def test_faculty_temporary_password_must_be_long_enough(admin_client):
    page = add_faculty(admin_client, temporary_password="short")

    assert "at least 8 characters" in page.get_data(as_text=True)


# --- Subjects ---


def test_admin_adds_a_subject_for_a_faculty_member(admin_client):
    page = submit(admin_client, "/admin/subjects/new", subject_form(admin_client))
    html = page.get_data(as_text=True)

    assert "CA261481" in html and "Machine Learning" in html and "R. Sharma" in html


def test_duplicate_subject_code_is_refused(admin_client):
    form = subject_form(admin_client)
    submit(admin_client, "/admin/subjects/new", form)

    page = submit(admin_client, "/admin/subjects/new", {**form, "subject_name": "Other"})

    assert "already used by another Subject" in page.get_data(as_text=True)


def test_subject_cannot_be_given_to_inactive_faculty(admin_client):
    form = subject_form(admin_client)
    admin_client.post(
        f"/admin/faculty/{form['faculty_id']}/deactivate",
        data={"csrf_token": _token(admin_client, "/admin/faculty/")},
    )

    page = submit(admin_client, "/admin/subjects/new", form)

    assert "Choose an active Faculty member" in page.get_data(as_text=True)


def test_registration_pages_are_admin_only(app, client):
    from test_auth import add_student

    add_student(app)
    login(client, "SSPU20260001", "SSPU20260001")
    submit(client, "/password", {"current_password": "SSPU20260001", "new_password": "my-new-pass", "confirm_password": "my-new-pass"})

    for url in ("/admin/students/", "/admin/faculty/", "/admin/subjects/", "/admin/students/new", "/admin/diagnostics/", "/admin/students/1/enrol"):
        assert client.get(url).status_code == 403, url
