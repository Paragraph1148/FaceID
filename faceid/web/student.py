"""Student pages (SPEC F6.3): a Student sees only their own student-wise report and session history."""

from flask import Blueprint, current_app, render_template

from faceid.reports import build
from faceid.reports.render import FORMATS
from faceid.store import queries
from faceid.web.auth import role_required
from faceid.web.reports import download, viewer

bp = Blueprint("student", __name__, url_prefix="/student")


def _own_report():
    # The Viewer is the Student, so `build` ignores any student_id in the request.
    return build("student", {}, viewer(), current_app.config["DEFAULTER_THRESHOLD"])


@bp.route("/")
@role_required("student")
def dashboard():
    return render_template("student/dashboard.html", table=_own_report(), formats=FORMATS,
                           history=queries.session_history(viewer().account_id))


@bp.route("/report/<fmt>")
@role_required("student")
def download_report(fmt):
    return download(_own_report(), "my-attendance", fmt)
