"""Faculty pages."""

from flask import Blueprint, render_template

from faceid.web.auth import role_required

bp = Blueprint("faculty", __name__, url_prefix="/faculty")


@bp.route("/")
@role_required("faculty")
def dashboard():
    return render_template("faculty/dashboard.html")
