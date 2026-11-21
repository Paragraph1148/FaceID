"""Student pages."""

from flask import Blueprint, render_template

from faceid.web.auth import role_required

bp = Blueprint("student", __name__, url_prefix="/student")


@bp.route("/")
@role_required("student")
def dashboard():
    return render_template("student/dashboard.html")
