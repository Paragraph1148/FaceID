"""Admin pages."""

from flask import Blueprint, render_template

from faceid.web.auth import role_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@role_required("admin")
def dashboard():
    return render_template("admin/dashboard.html")
