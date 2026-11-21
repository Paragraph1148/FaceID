"""FaceID: face-recognition attendance system."""

__version__ = "0.2.0"

import warnings

# face_recognition_models imports pkg_resources, which warns on every start. Harmless while setuptools < 82.
warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)

import atexit
import secrets
from pathlib import Path

from flask import Flask, render_template

from faceid import cli, settings
from faceid.camera import WebcamSource
from faceid.feed import CameraFeed
from faceid.vision import DlibEngine
from faceid.store import db


def create_app(config: dict | None = None, instance_path: str | None = None) -> Flask:
    """Build the Flask app. `config` overrides `instance/config.py` (used by tests)."""
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    app.config.from_pyfile("config.py", silent=True)
    if config:
        app.config.update(config)
    settings.apply_defaults(app.config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _instance_secret_key(Path(app.instance_path))

    app.teardown_appcontext(db.close)
    cli.register(app)
    _attach_camera_and_engine(app)

    from faceid.web import admin, auth, diagnostics, enrolment, faculty, student

    auth.login_manager.init_app(app)
    app.jinja_env.globals["csrf_token"] = auth.csrf_token
    for blueprint in (auth.bp, admin.bp, diagnostics.bp, enrolment.bp, faculty.bp, student.bp):
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


def _instance_secret_key(instance_dir: Path) -> str:
    """Read the secret key from the untracked instance folder, generating it on first run (N6)."""
    key_file = instance_dir / "secret_key"
    if not key_file.exists():
        instance_dir.mkdir(parents=True, exist_ok=True)
        key_file.write_text(secrets.token_hex(32), encoding="ascii")
    return key_file.read_text(encoding="ascii").strip()


def _attach_camera_and_engine(app: Flask) -> None:
    """One shared camera feed and face engine per server. Tests pass fakes as CAMERA_SOURCE and FACE_ENGINE."""
    config = app.config
    open_camera = config.get("CAMERA_SOURCE") or WebcamSource
    app.extensions["camera_feed"] = CameraFeed(
        lambda: open_camera(config["CAMERA_INDEX"], config["CAMERA_WIDTH"], config["CAMERA_HEIGHT"])
    )
    app.extensions["face_engine"] = config.get("FACE_ENGINE") or DlibEngine(
        config["DETECTOR"], config["DETECTION_SCALE"], config["DETECTION_UPSAMPLE"]
    )
    app.extensions["enrolment_drafts"] = {}  # student_id -> EnrolmentDraft, in memory only (ADR 0002)
    # Release the webcam on exit; a camera thread still running at interpreter shutdown can crash it.
    atexit.register(app.extensions["camera_feed"].stop)
