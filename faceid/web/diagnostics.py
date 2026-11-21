"""Camera diagnostics page (Admin only). The work happens in `faceid.diagnostics`."""

import platform

import cv2
from flask import Blueprint, Response, current_app, render_template

from faceid import diagnostics, vision
from faceid.web.auth import role_required

bp = Blueprint("diagnostics", __name__, url_prefix="/admin/diagnostics")


@bp.route("/")
@role_required("admin")
def page():
    config = current_app.config
    facts = {
        "Operating system": f"{platform.system()} {platform.release()}",
        "Python": platform.python_version(),
        "OpenCV": cv2.__version__,
        "Face engine": vision.engine_description(),
        "Detector": f"{config['DETECTOR']}, scale {config['DETECTION_SCALE']}, upsample {config['DETECTION_UPSAMPLE']}",
        "Requested camera": f"#{config['CAMERA_INDEX']} at {config['CAMERA_WIDTH']}x{config['CAMERA_HEIGHT']} MJPG",
    }
    return render_template("admin/diagnostics.html", facts=facts)


@bp.route("/stream")
@role_required("admin")
def stream():
    frames = diagnostics.mjpeg_frames(dict(current_app.config))
    return Response(frames, mimetype="multipart/x-mixed-replace; boundary=frame")
