"""Face Enrolment pages (SPEC F3): the Admin captures five guided poses of a Student, then saves them."""

import secrets

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from faceid.camera import CameraUnavailable
from faceid.enrolment import POSES, Accepted, EnrolmentDraft, Rejected
from faceid.store import people
from faceid.web.auth import role_required
from faceid.web.preview import enrolment_rules, preview_response

bp = Blueprint("enrolment", __name__, url_prefix="/admin/students/<int:student_id>/enrol")


@bp.url_value_preprocessor
def load_student(endpoint, values):
    # Every route here is for one existing, active Student.
    student = people.get_student(values["student_id"])
    if student is None:
        abort(404)
    request.student = student


def _owner() -> str:
    """This browser login's key for its own drafts."""
    if "enrolment_owner" not in session:
        session["enrolment_owner"] = secrets.token_hex(8)
    return session["enrolment_owner"]


def _draft(student_id: int) -> EnrolmentDraft:
    return current_app.extensions["enrolment_drafts"].get(_owner(), student_id)


def _back(student_id):
    return redirect(url_for("enrolment.page", student_id=student_id))


@bp.before_request
def require_active_student():
    if request.student and not request.student["is_active"]:
        flash(f"Reactivate {request.student['name']} before enrolling their face.", "danger")
        return redirect(url_for("admin.students"))
    return None


@bp.route("")
@role_required("admin")
def page(student_id):
    return render_template("admin/enrol.html", student=request.student, poses=POSES, draft=_draft(student_id))


@bp.route("/stream")
@role_required("admin")
def stream(student_id):
    return preview_response()


@bp.route("/capture", methods=["POST"])
@role_required("admin")
def capture(student_id):
    pose = request.form.get("pose", "")
    if pose not in POSES:
        abort(400, "Unknown pose.")
    try:
        frame = current_app.extensions["camera_feed"].latest_frame()
    except CameraUnavailable as error:
        flash(str(error), "danger")
        return _back(student_id)
    others = people.encodings_of_other_students(student_id)
    result = _draft(student_id).capture(pose, frame, current_app.extensions["face_engine"], others, enrolment_rules())
    if isinstance(result, Accepted):
        flash(f"Captured: {POSES[pose]}.", "success")
    else:
        flash(result.reason, "danger")
    return _back(student_id)


@bp.route("/save", methods=["POST"])
@role_required("admin")
def save(student_id):
    result = _draft(student_id).ready_to_save(people.encodings_of_other_students(student_id), enrolment_rules())
    if isinstance(result, Rejected):
        flash(result.reason, "danger")
        return _back(student_id)
    people.replace_encodings(student_id, result)
    current_app.extensions["enrolment_drafts"].discard(_owner(), student_id)
    flash(f"Face Enrolment saved for {request.student['name']}.", "success")
    return redirect(url_for("admin.students"))


@bp.route("/cancel", methods=["POST"])
@role_required("admin")
def cancel(student_id):
    current_app.extensions["enrolment_drafts"].discard(_owner(), student_id)
    flash("Captures discarded.", "secondary")
    return _back(student_id)
