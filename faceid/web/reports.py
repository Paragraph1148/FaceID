"""Report pages and downloads for the Admin and Faculty (SPEC F6). Students see theirs on their dashboard."""

from flask import Blueprint, Response, abort, current_app, render_template, request
from flask_login import current_user

from faceid.reports import KINDS, BadReportRequest, Viewer, build
from faceid.reports.render import FORMATS, render
from faceid.store import people, teaching
from faceid.web.auth import role_required

bp = Blueprint("reports", __name__, url_prefix="/reports")


def viewer() -> Viewer:
    return Viewer(current_user.role, current_user.account_id)


def build_for_request(kind: str):
    return build(kind, request.args, viewer(), current_app.config["DEFAULTER_THRESHOLD"])


def download(table, name: str, fmt: str) -> Response:
    """The Table as a file to save. `name` is the file name without its extension."""
    if fmt not in FORMATS:
        abort(404)
    return Response(render(table, fmt), mimetype=FORMATS[fmt],
                    headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})


def _file_name(kind: str) -> str:
    """e.g. defaulters-3-75: the report and what it was asked for, with only safe characters."""
    parts = [kind, *request.args.values()]
    return "-".join("".join(c for c in part if (c.isascii() and c.isalnum()) or c == "-") for part in parts if part)


def _index(problem: str | None = None, status: int = 200):
    faculty_id = current_user.account_id if current_user.role == "faculty" else None
    return render_template(
        "reports/index.html", kinds=KINDS, problem=problem, args=request.args,
        subjects=teaching.list_subjects(faculty_id), students=people.list_students(),
        default_threshold=current_app.config["DEFAULTER_THRESHOLD"],
    ), status


@bp.route("/")
@role_required("admin", "faculty")
def index():
    return _index()


@bp.route("/<kind>")
@role_required("admin", "faculty")
def view(kind):
    try:
        table = build_for_request(kind)
    except BadReportRequest as problem:
        return _index(str(problem), 400)
    return render_template("reports/view.html", table=table, kind=kind, formats=FORMATS)


@bp.route("/<kind>/<fmt>")
@role_required("admin", "faculty")
def download_report(kind, fmt):
    try:
        table = build_for_request(kind)
    except BadReportRequest as problem:
        return _index(str(problem), 400)
    return download(table, _file_name(kind), fmt)
