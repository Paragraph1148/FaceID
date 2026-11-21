"""FaceID: face-recognition attendance system."""

__version__ = "0.1.0.dev0"

import warnings

# face_recognition_models imports pkg_resources, which warns on every start. Harmless while setuptools < 82.
warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)

from flask import Flask, render_template

from faceid import cli
from faceid.store import db


def create_app(config=None):
    """Build the Flask app. `config` overrides `instance/config.py` (used by tests)."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile("config.py", silent=True)
    if config:
        app.config.update(config)

    app.teardown_appcontext(db.close)
    cli.register(app)

    from faceid.web import admin, auth, faculty, student

    auth.login_manager.init_app(app)
    app.jinja_env.globals["csrf_token"] = auth.csrf_token
    for blueprint in (auth.bp, admin.bp, faculty.bp, student.bp):
        app.register_blueprint(blueprint)

    @app.before_request
    def require_current_schema():
        # Checked once per process after it first succeeds, so normal requests pay nothing.
        if app.config.get("_SCHEMA_OK"):
            return None
        if not db.is_up_to_date(app.config):
            return render_template("schema_outdated.html"), 503
        app.config["_SCHEMA_OK"] = True
        return None

    app.before_request(auth.check_csrf)
    app.before_request(auth.force_password_change)

    return app
