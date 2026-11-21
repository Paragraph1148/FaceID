"""Face Enrolment pages (SPEC F3): the Admin captures five guided poses of a Student, then saves them."""

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, url_for

from faceid.camera import CameraUnavailable
from faceid.enrolment import POSES, Accepted, EnrolmentDraft, EnrolmentRules, assess_capture
from faceid.preview import mjpeg_preview
from faceid.store import people
from faceid.web.auth import role_required

bp = Blueprint("enrolment", __name__, url_prefix="/admin/students/<int:student_id>/enrol")


def _student_or_404(student_id: int) -> dict:
    student = people.get_student(student_id)
    if student is None:
        abort(404)
    return student


def _draft(student_id: int) -> EnrolmentDraft:
    drafts = current_app.extensions["enrolment_drafts"]
    return drafts.setdefault(student_id, EnrolmentDraft(student_id))


def _rules() -> EnrolmentRules:
    config = current_app.config
    return EnrolmentRules(config["MIN_FACE_WIDTH"], config["MIN_SHARPNESS"], config["TOLERANCE"])


@bp.route("")
@role_required("admin")
def page(student_id):
    student = _student_or_404(student_id)
    return render_template("admin/enrol.html", student=student, poses=POSES, draft=_draft(student_id))


@bp.route("/stream")
@role_required("admin")
def stream(student_id):
    rules = _rules()
    frames = mjpeg_preview(
        current_app.extensions["camera_feed"], current_app.extensions["face_engine"], rules.min_face_width, rules.min_sharpness
    )
    return Response(frames, mimetype="multipart/x-mixed-replace; boundary=frame")


@bp.route("/capture", methods=["POST"])
@role_required("admin")
def capture(student_id):
    _student_or_404(student_id)
    pose = request.form.get("pose", "")
    if pose not in POSES:
        abort(400, "Unknown pose.")
    try:
        frame = current_app.extensions["camera_feed"].latest_frame()
    except CameraUnavailable as error:
        flash(str(error), "danger")
        return redirect(url_for("enrolment.page", student_id=student_id))
    result = assess_capture(frame, current_app.extensions["face_engine"], people.encodings_of_other_students(student_id), _rules())
    del frame  # the Capture is discarded here; only its encoding is kept (F3.3)
    if isinstance(result, Accepted):
        _draft(student_id).accept(pose, result.encoding)
        flash(f"Captured: {POSES[pose]}.", "success")
    else:
        flash(result.reason, "danger")
    return redirect(url_for("enrolment.page", student_id=student_id))


@bp.route("/save", methods=["POST"])
@role_required("admin")
def save(student_id):
    student = _student_or_404(student_id)
    draft = _draft(student_id)
    if draft.missing():
        flash(f"Capture all {len(POSES)} poses first.", "danger")
        return redirect(url_for("enrolment.page", student_id=student_id))
    people.replace_encodings(student_id, draft.encodings())
    current_app.extensions["enrolment_drafts"].pop(student_id, None)
    flash(f"Face Enrolment saved for {student['name']}.", "success")
    return redirect(url_for("admin.students"))


@bp.route("/cancel", methods=["POST"])
@role_required("admin")
def cancel(student_id):
    current_app.extensions["enrolment_drafts"].pop(student_id, None)
    flash("Captures discarded.", "secondary")
    return redirect(url_for("enrolment.page", student_id=student_id))
