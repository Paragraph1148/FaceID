"""The live preview response, shared by the diagnostics and enrolment pages."""

from flask import Response, current_app

from faceid.enrolment import EnrolmentRules
from faceid.preview import mjpeg_preview


def enrolment_rules() -> EnrolmentRules:
    config = current_app.config
    return EnrolmentRules(config["MIN_FACE_WIDTH"], config["MIN_SHARPNESS"], config["TOLERANCE"])


def preview_response() -> Response:
    frames = mjpeg_preview(current_app.extensions["camera_feed"], current_app.extensions["face_engine"], enrolment_rules())
    return Response(frames, mimetype="multipart/x-mixed-replace; boundary=frame")
