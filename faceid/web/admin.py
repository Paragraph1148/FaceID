"""Admin pages: registration of Students, Faculty and Subjects (SPEC F2)."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from mysql.connector import IntegrityError

from faceid import registration
from faceid.store import db, people, teaching
from faceid.web.auth import role_required

bp = Blueprint("admin", __name__, url_prefix="/admin")

DUPLICATE_MESSAGES = {
    "enrollment_no": "This Enrolment Number is already used by another Student.",
    "email": "This email is already used by another {who}.",
    "subject_code": "This Subject Code is already used by another Subject.",
}


def _duplicate_error(error, who):
    """Turn a duplicate-key error into {field: message}, or re-raise anything else."""
    field = db.duplicate_field(error)
    if field is None:
        raise error
    return {field: DUPLICATE_MESSAGES.get(field, "Already in use.").format(who=who)}


@bp.route("/")
@role_required("admin")
def dashboard():
    return render_template("admin/dashboard.html")


# --- Students ---


@bp.route("/students/")
@role_required("admin")
def students():
    return render_template("admin/students.html", students=people.list_students())


@bp.route("/students/new", methods=["GET", "POST"])
@bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def student_form(student_id=None):
    existing = people.get_student(student_id) if student_id else None
    if student_id and not existing:
        abort(404)
    values, errors = existing or {}, {}
    if request.method == "POST":
        values, errors = registration.clean_student(request.form)
        if not errors:
            try:
                if existing:
                    people.update_student(student_id, **values)
                else:
                    people.create_student(**values)
            except IntegrityError as error:
                errors = _duplicate_error(error, "Student")
        if not errors:
            flash(f"Saved {values['name']}.", "success")
            return redirect(url_for("admin.students"))
    return render_template("admin/student_form.html", values=values, errors=errors, existing=existing)


@bp.route("/students/<int:student_id>/<any(activate, deactivate):action>", methods=["POST"])
@role_required("admin")
def student_active(student_id, action):
    people.set_active("student", student_id, action == "activate")
    return redirect(url_for("admin.students"))


@bp.route("/students/<int:student_id>/reset-password", methods=["POST"])
@role_required("admin")
def student_reset_password(student_id):
    people.reset_student_password(student_id)
    flash("Password reset to the Enrolment Number. The Student must change it at next login.", "success")
    return redirect(url_for("admin.students"))


# --- Faculty ---


@bp.route("/faculty/")
@role_required("admin")
def faculty():
    return render_template("admin/faculty.html", faculty=people.list_faculty())


@bp.route("/faculty/new", methods=["GET", "POST"])
@bp.route("/faculty/<int:faculty_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def faculty_form(faculty_id=None):
    existing = people.get_faculty(faculty_id) if faculty_id else None
    if faculty_id and not existing:
        abort(404)
    values, errors = existing or {}, {}
    if request.method == "POST":
        values, errors = registration.clean_faculty(request.form, is_new=existing is None)
        if not errors:
            try:
                if existing:
                    people.update_faculty(faculty_id, **values)
                else:
                    people.create_faculty(**values)
            except IntegrityError as error:
                errors = _duplicate_error(error, "Faculty member")
        if not errors:
            flash(f"Saved {values['name']}.", "success")
            return redirect(url_for("admin.faculty"))
    return render_template("admin/faculty_form.html", values=values, errors=errors, existing=existing)


@bp.route("/faculty/<int:faculty_id>/<any(activate, deactivate):action>", methods=["POST"])
@role_required("admin")
def faculty_active(faculty_id, action):
    people.set_active("faculty", faculty_id, action == "activate")
    return redirect(url_for("admin.faculty"))


# --- Subjects ---


@bp.route("/subjects/")
@role_required("admin")
def subjects():
    return render_template("admin/subjects.html", subjects=teaching.list_subjects())


@bp.route("/subjects/new", methods=["GET", "POST"])
@bp.route("/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def subject_form(subject_id=None):
    existing = teaching.get_subject(subject_id) if subject_id else None
    if subject_id and not existing:
        abort(404)
    active_faculty = people.list_faculty(active_only=True)
    values, errors = existing or {}, {}
    if request.method == "POST":
        values, errors = registration.clean_subject(request.form, {f["faculty_id"] for f in active_faculty})
        if not errors:
            try:
                if existing:
                    teaching.update_subject(subject_id, **values)
                else:
                    teaching.create_subject(**values)
            except IntegrityError as error:
                errors = _duplicate_error(error, "Subject")
        if not errors:
            flash(f"Saved {values['subject_code']}.", "success")
            return redirect(url_for("admin.subjects"))
    return render_template(
        "admin/subject_form.html", values=values, errors=errors, existing=existing, faculty=active_faculty
    )


@bp.route("/subjects/<int:subject_id>/<any(activate, deactivate):action>", methods=["POST"])
@role_required("admin")
def subject_active(subject_id, action):
    teaching.set_subject_active(subject_id, action == "activate")
    return redirect(url_for("admin.subjects"))
