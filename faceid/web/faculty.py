"""Faculty pages (SPEC F4, F5): Class Sessions, the live camera, closing and Manual Override.

`class_session` is a Class Session row; Flask's `session` (the login) is a different thing.
"""

from datetime import datetime

from flask import Blueprint, Response, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from faceid.attendance import STATUSES, clean_class_session, clean_override, suggested_times
from faceid.live import LiveSession
from faceid.preview import mjpeg_live
from faceid.store import attendance, teaching
from faceid.store.attendance import CannotOpen
from faceid.web.auth import role_required

bp = Blueprint("faculty", __name__, url_prefix="/faculty")


def _now() -> datetime:
    return current_app.extensions["clock"]()


def _live() -> LiveSession:
    return current_app.extensions["live"]


def _own_class_session(session_id: int) -> dict:
    """The Class Session, if it belongs to the logged-in Faculty member; otherwise 404."""
    class_session = teaching.get_class_session(session_id)
    if class_session is None or class_session["faculty_id"] != current_user.account_id:
        abort(404)
    return class_session


def _back(session_id: int, anchor: str = ""):
    return redirect(url_for("faculty.session_page", session_id=session_id) + anchor)


@bp.route("/")
@role_required("faculty")
def dashboard():
    return render_template(
        "faculty/dashboard.html",
        class_sessions=teaching.list_class_sessions(current_user.account_id),
        open_session=teaching.find_open_class_session(),
    )


@bp.route("/sessions/new", methods=["GET", "POST"])
@role_required("faculty")
def new_session():
    subjects = teaching.subjects_taught_by(current_user.account_id)
    start, end = suggested_times(_now())
    values, errors = {"start_time": start.strftime("%H:%M"), "end_time": end.strftime("%H:%M")}, {}
    if request.method == "POST":
        cleaned, errors = clean_class_session(request.form, {s["subject_id"] for s in subjects}, _now().date())
        if not errors:
            try:
                session_id = attendance.open_class_session(current_user.account_id, **cleaned)
            except CannotOpen as reason:
                flash(str(reason), "danger")
            else:
                return _back(session_id)
        values = request.form
    return render_template("faculty/session_form.html", subjects=subjects, values=values, errors=errors, today=_now().date())


@bp.route("/sessions/<int:session_id>")
@role_required("faculty")
def session_page(session_id):
    class_session = _own_class_session(session_id)
    if class_session["status"] == "open":
        _live().ensure_running(session_id)  # also resumes recognition after a server restart (ADR 0007)
    return render_template(
        "faculty/session.html", class_session=class_session, records=attendance.records(session_id), statuses=STATUSES
    )


@bp.route("/sessions/<int:session_id>/stream")
@role_required("faculty")
def session_stream(session_id):
    if _own_class_session(session_id)["status"] != "open":
        abort(404)
    frames = mjpeg_live(current_app.extensions["camera_feed"], _live(), session_id)
    return Response(frames, mimetype="multipart/x-mixed-replace; boundary=frame")


@bp.route("/sessions/<int:session_id>/status")
@role_required("faculty")
def session_status(session_id):
    """What the open Class Session's page refreshes every two seconds (F4.4)."""
    class_session = _own_class_session(session_id)
    return jsonify(
        status=class_session["status"],
        attended=class_session["attended"],
        expected=class_session["expected"],
        marked=attendance.recently_marked(session_id),
        **_live().report(session_id),
    )


@bp.route("/sessions/<int:session_id>/close", methods=["POST"])
@role_required("faculty")
def close_session(session_id):
    _own_class_session(session_id)
    _live().stop_if(session_id)
    if attendance.close(session_id):
        flash("Class Session closed. Students not marked are absent.", "success")
    return _back(session_id)


@bp.route("/sessions/<int:session_id>/cancel", methods=["POST"])
@role_required("faculty")
def cancel_session(session_id):
    _own_class_session(session_id)
    if attendance.cancel(session_id):
        _live().stop_if(session_id)
        flash("Class Session cancelled. It counts towards nobody's attendance.", "secondary")
    else:
        flash("Only an open Class Session can be cancelled.", "danger")
    return _back(session_id)


@bp.route("/sessions/<int:session_id>/records/<int:student_id>", methods=["POST"])
@role_required("faculty")
def override_record(session_id, student_id):
    class_session = _own_class_session(session_id)
    if class_session["status"] == "cancelled":
        flash("A cancelled Class Session's records can't be changed.", "danger")
        return _back(session_id)
    change, problem = clean_override(request.form, class_session["session_minutes"])
    if problem:
        flash(problem, "danger")
    elif attendance.override(session_id, student_id, *change, at=_now()):
        flash("Attendance Record updated by Manual Override.", "success")
    else:
        abort(404)
    return _back(session_id, "#records")
