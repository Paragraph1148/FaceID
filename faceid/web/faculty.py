"""Faculty pages (SPEC F4, F5): Class Sessions, the live camera, closing and Manual Override."""

from datetime import datetime, timedelta

from flask import Blueprint, Response, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from faceid.attendance import clean_class_session, clean_override
from faceid.preview import mjpeg_live
from faceid.store import attendance, teaching
from faceid.store.attendance import CannotOpen
from faceid.web.auth import role_required

bp = Blueprint("faculty", __name__, url_prefix="/faculty")


def _now() -> datetime:
    clock = current_app.config.get("CLOCK") or datetime.now
    return clock()


def _own_session(session_id: int) -> dict:
    """The Class Session, if it belongs to the logged-in Faculty member; otherwise 404."""
    session = teaching.get_class_session(session_id)
    if session is None or session["faculty_id"] != current_user.account_id:
        abort(404)
    return session


def _live():
    return current_app.extensions["live"]


def _stop_recognising(session_id: int) -> None:
    if _live().session_id == session_id:
        _live().stop()


@bp.route("/")
@role_required("faculty")
def dashboard():
    return render_template(
        "faculty/dashboard.html",
        sessions=teaching.list_class_sessions(current_user.account_id),
        open_session=teaching.the_open_class_session(),
    )


@bp.route("/sessions/new", methods=["GET", "POST"])
@role_required("faculty")
def new_session():
    subjects = teaching.subjects_taught_by(current_user.account_id)
    now = _now()
    values, errors = {"start_time": now.strftime("%H:%M"), "end_time": (now + timedelta(hours=1)).strftime("%H:%M")}, {}
    if request.method == "POST":
        values, errors = clean_class_session(request.form, {s["subject_id"] for s in subjects}, now.date())
        if not errors:
            try:
                session_id = attendance.open_class_session(current_user.account_id, **values)
            except CannotOpen as reason:
                flash(str(reason), "danger")
            else:
                return redirect(url_for("faculty.session_page", session_id=session_id))
        values = {**values, **{k: request.form.get(k, "") for k in ("start_time", "end_time", "room_no")}}
    return render_template("faculty/session_form.html", subjects=subjects, values=values, errors=errors, today=now.date())


@bp.route("/sessions/<int:session_id>")
@role_required("faculty")
def session_page(session_id):
    session = _own_session(session_id)
    if session["status"] == "open":
        _live().ensure_running(session_id)  # also resumes recognition after a server restart (ADR 0007)
    return render_template("faculty/session.html", session=session, records=attendance.records(session_id))


@bp.route("/sessions/<int:session_id>/stream")
@role_required("faculty")
def session_stream(session_id):
    session = _own_session(session_id)
    if session["status"] != "open":
        abort(404)
    frames = mjpeg_live(current_app.extensions["camera_feed"], _live(), session_id)
    return Response(frames, mimetype="multipart/x-mixed-replace; boundary=frame")


@bp.route("/sessions/<int:session_id>/status")
@role_required("faculty")
def session_status(session_id):
    """What the open session's page refreshes every two seconds (F4.4)."""
    session = _own_session(session_id)
    live = _live()
    running = live.session_id == session_id
    marked = sorted(
        (r for r in attendance.records(session_id) if r["status"] != "absent"), key=lambda r: r["marked_at"], reverse=True
    )
    return jsonify(
        status=session["status"],
        attended=session["attended"],
        expected=session["expected"],
        recognising=running,
        fps=round(live.fps, 1) if running else None,
        error=live.error if running else None,
        marked=[{"name": r["name"], "status": r["status"], "minutes_late": r["minutes_late"]} for r in marked],
    )


@bp.route("/sessions/<int:session_id>/close", methods=["POST"])
@role_required("faculty")
def close_session(session_id):
    session = _own_session(session_id)
    if session["status"] == "open":
        _stop_recognising(session_id)
        attendance.close(session_id)
        flash("Class Session closed. Students not marked are absent.", "success")
    return redirect(url_for("faculty.session_page", session_id=session_id))


@bp.route("/sessions/<int:session_id>/cancel", methods=["POST"])
@role_required("faculty")
def cancel_session(session_id):
    session = _own_session(session_id)
    if session["status"] != "cancelled":
        _stop_recognising(session_id)
        attendance.cancel(session_id)
        flash("Class Session cancelled. It counts towards nobody's attendance.", "secondary")
    return redirect(url_for("faculty.session_page", session_id=session_id))


@bp.route("/sessions/<int:session_id>/records/<int:student_id>", methods=["POST"])
@role_required("faculty")
def override_record(session_id, student_id):
    session = _own_session(session_id)
    if session["status"] == "cancelled":
        flash("A cancelled Class Session's records can't be changed.", "danger")
        return redirect(url_for("faculty.session_page", session_id=session_id))
    change, problem = clean_override(request.form, session["session_minutes"])
    if problem:
        flash(problem, "danger")
    elif not attendance.override(session_id, student_id, *change, at=_now()):
        abort(404)
    else:
        flash("Attendance Record updated by Manual Override.", "success")
    return redirect(url_for("faculty.session_page", session_id=session_id) + "#records")
