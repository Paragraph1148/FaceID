"""Login, logout, password change, role checks and CSRF protection (SPEC F1, N6)."""

import secrets
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user

from faceid.passwords import check_password, problem_with
from faceid.store import people

bp = Blueprint("auth", __name__)
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = None

HOME_FOR_ROLE = {"admin": "admin.dashboard", "faculty": "faculty.dashboard", "student": "student.dashboard"}


class Account(UserMixin):
    """The logged-in person. Flask-Login identifies them as "role:id", e.g. "student:7"."""

    def __init__(self, role, row):
        self.role = role
        self.account_id = row["id"]
        self.name = row["name"]
        self.password_hash = row["password_hash"]
        self.must_change_password = bool(row["must_change_password"])

    def get_id(self):
        return f"{self.role}:{self.account_id}"


@login_manager.user_loader
def load_account(user_id):
    role, _, account_id = user_id.partition(":")
    if role not in HOME_FOR_ROLE:
        return None
    row = people.get_account(role, int(account_id))
    return Account(role, row) if row else None


def role_required(role):
    """Allow only logged-in accounts of `role`; others get 403 Forbidden."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


# --- CSRF: one random token per browser session, required on every POST ---


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf_token", "")):
            abort(400, "Form expired or invalid. Go back, reload the page and try again.")


def force_password_change():
    allowed = {"auth.change_password", "auth.logout", "static"}
    if current_user.is_authenticated and current_user.must_change_password and request.endpoint not in allowed:
        return redirect(url_for("auth.change_password"))
    return None


# --- Pages ---


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for(HOME_FOR_ROLE[current_user.role]))
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        found = people.find_login(identifier)
        if found and _password_matches(*found, password):
            login_user(Account(*found))
            return redirect(url_for("auth.index"))
        flash("Wrong login or password.", "danger")
    return render_template("auth/login.html")


def _password_matches(role: str, row: dict, password: str) -> bool:
    if check_password(password, row["password_hash"]):
        return True
    # A Student's temporary password is their Enrolment Number, stored in capitals: accept it typed in any case.
    return role == "student" and bool(row["must_change_password"]) and check_password(password.upper(), row["password_hash"])


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        new = request.form.get("new_password", "")
        error = problem_with(new)
        row = {"password_hash": current_user.password_hash, "must_change_password": current_user.must_change_password}
        if not _password_matches(current_user.role, row, request.form.get("current_password", "")):
            error = "Current password is wrong."
        elif new != request.form.get("confirm_password", ""):
            error = "The two passwords do not match."
        elif error is None and check_password(new, current_user.password_hash):
            error = "The new password must be different from the current one."
        if error:
            flash(error, "danger")
        else:
            people.set_password(current_user.role, current_user.account_id, new)
            flash("Password changed.", "success")
            return redirect(url_for("auth.index"))
    return render_template("auth/password.html")
