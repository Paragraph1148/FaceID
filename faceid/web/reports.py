"""Report pages and downloads for the Admin and Faculty (SPEC F6). Students see theirs on their dashboard."""

from flask import Blueprint, Response, abort, current_app, render_template, request
from flask_login import current_user

from faceid.reports import KINDS, BadReportRequest, Viewer, build, form_choices
from faceid.reports.render import FORMATS, media_type, render
from faceid.reports.tables import Table
from faceid.web.auth import role_required

bp = Blueprint("reports", __name__, url_prefix="/reports")


def viewer() -> Viewer:
    return Viewer(current_user.role, current_user.account_id)


def download(table: Table, name: str, fmt: str) -> Response:
    """The Table as a file to save. `name` is the file name without its extension."""
    if fmt not in FORMATS:
        abort(404)
    return Response(render(table, fmt), mimetype=media_type(fmt),
                    headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})


def _report_args() -> dict[str, str]:
    """What the report was asked for. `kind` and `fmt` are in the URL path, so the query string can't override them."""
    return {name: value for name, value in request.args.items() if name not in ("kind", "fmt")}


def _file_name(kind: str) -> str:
    """e.g. defaulters-3-75: the report and what it was asked for, with only safe characters."""
    parts = [kind, *_report_args().values()]
    return "-".join("".join(c for c in part if (c.isascii() and c.isalnum()) or c == "-") for part in parts if part)


def _index(problem: str | None = None, status: int = 200) -> tuple[str, int]:
    return render_template("reports/index.html", kinds=KINDS, problem=problem, args=request.args,
                           default_threshold=current_app.config["DEFAULTER_THRESHOLD"], **form_choices(viewer())), status


@bp.route("/")
@role_required("admin", "faculty")
def index():
    return _index()


@bp.route("/<kind>")
@bp.route("/<kind>/<fmt>")
@role_required("admin", "faculty")
def view(kind, fmt=None):
    """The report in the browser, or as a file when a format is given."""
    try:
        table = build(kind, _report_args(), viewer(), current_app.config["DEFAULTER_THRESHOLD"])
    except BadReportRequest as problem:
        return _index(str(problem), 400)
    if fmt is not None:
        return download(table, _file_name(kind), fmt)
    return render_template("reports/view.html", table=table, kind=kind, params=_report_args(), formats=FORMATS)
