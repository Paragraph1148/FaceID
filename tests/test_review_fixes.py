"""Regression tests for bugs found in the v0.1.0 review."""

from conftest import create_admin, csrf_token, login, submit
from test_auth import add_student
from test_registration import FACULTY, STUDENT


def test_logout_needs_a_form_post_so_other_sites_cannot_log_people_out(admin_client):
    assert admin_client.get("/logout").status_code == 405
    admin_client.post("/logout", data={"csrf_token": csrf_token(admin_client, "/admin/")})
    assert admin_client.get("/admin/").status_code == 302


def test_changing_password_requires_the_current_password(app, client):
    add_student(app)
    login(client, "SSPU20260001", "SSPU20260001")

    page = submit(client, "/password", {"current_password": "wrong", "new_password": "my-new-pass", "confirm_password": "my-new-pass"})

    assert "Current password is wrong" in page.get_data(as_text=True)


def test_resetting_an_unknown_student_is_not_found(admin_client):
    response = admin_client.post("/admin/students/999/reset-password", data={"csrf_token": csrf_token(admin_client, "/admin/")})

    assert response.status_code == 404


def test_an_email_belongs_to_one_account_across_all_roles(admin_client):
    page = submit(admin_client, "/admin/faculty/new", {**FACULTY, "email": "admin@college.test"})
    assert "already used by another account" in page.get_data(as_text=True)

    submit(admin_client, "/admin/faculty/new", FACULTY)
    page = submit(admin_client, "/admin/students/new", {**STUDENT, "email": FACULTY["email"]})
    assert "already used by another account" in page.get_data(as_text=True)


def test_create_admin_refuses_an_email_a_faculty_member_has(app, admin_client):
    submit(admin_client, "/admin/faculty/new", FACULTY)

    result = app.test_cli_runner().invoke(
        args=["create-admin"], input=f"second\n{FACULTY['email']}\nadmin-pass-2\nadmin-pass-2\n"
    )

    assert result.exit_code != 0
    assert "already used" in result.output


def test_enrolment_number_is_case_insensitive_for_login_and_temporary_password(admin_client, app):
    submit(admin_client, "/admin/students/new", {**STUDENT, "enrollment_no": "sspu20260001"})

    page = login(app.test_client(), "sspu20260001", "sspu20260001")

    assert "Choose a new password" in page.get_data(as_text=True)


def test_editing_the_enrolment_number_moves_the_temporary_password_with_it(admin_client, app):
    submit(admin_client, "/admin/students/new", STUDENT)
    submit(admin_client, "/admin/students/1/edit", {**STUDENT, "enrollment_no": "SSPU20260099"})

    page = login(app.test_client(), "SSPU20260099", "SSPU20260099")

    assert "Choose a new password" in page.get_data(as_text=True)


def test_edit_pages_never_receive_password_hashes(admin_client):
    submit(admin_client, "/admin/faculty/new", FACULTY)
    import faceid.store.people as people

    with admin_client.application.app_context():
        assert "password_hash" not in people.get_faculty(1)


def test_a_secret_key_is_generated_into_the_instance_folder_when_missing(test_config, tmp_path):
    from faceid import create_app

    config = {key: value for key, value in test_config.items() if key != "SECRET_KEY"}
    first = create_app(config, instance_path=str(tmp_path))
    second = create_app(config, instance_path=str(tmp_path))

    assert first.secret_key and first.secret_key == second.secret_key
    assert (tmp_path / "secret_key").exists()
