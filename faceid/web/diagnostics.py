"""Camera diagnostics (SPEC §8, v0.1.0): proves the webcam and dlib work on this machine.

Shows the live feed with HOG face boxes and the processing speed. One viewer at a time, because there is one camera.
"""

import platform
import threading
import time

import cv2
import dlib
from flask import Blueprint, Response, current_app, render_template

from faceid.camera import CameraUnavailable, WebcamSource
from faceid.vision import DlibEngine
from faceid.web.auth import role_required

bp = Blueprint("diagnostics", __name__, url_prefix="/admin/diagnostics")
camera_in_use = threading.Lock()


@bp.route("/")
@role_required("admin")
def page():
    config = current_app.config
    facts = {
        "Operating system": f"{platform.system()} {platform.release()}",
        "Python": platform.python_version(),
        "OpenCV": cv2.__version__,
        "dlib": f"{dlib.__version__} (CUDA: {'yes' if dlib.DLIB_USE_CUDA else 'no'})",
        "Detector": f"{config['DETECTOR']}, scale {config['DETECTION_SCALE']}, upsample {config['DETECTION_UPSAMPLE']}",
        "Requested camera": f"#{config['CAMERA_INDEX']} at {config['CAMERA_WIDTH']}x{config['CAMERA_HEIGHT']} MJPG",
    }
    return render_template("admin/diagnostics.html", facts=facts)


def _annotated_frames(config):
    if not camera_in_use.acquire(blocking=False):
        yield _jpeg_part(_message_frame("Camera is in use by another page or session."))
        return
    source = None
    try:
        source = WebcamSource(config["CAMERA_INDEX"], config["CAMERA_WIDTH"], config["CAMERA_HEIGHT"])
        info = source.info()
        engine = DlibEngine(config["DETECTOR"], config["DETECTION_SCALE"], config["DETECTION_UPSAMPLE"])
        last = time.perf_counter()
        fps = 0.0
        while True:
            frame = source.read()
            if frame is None:
                yield _jpeg_part(_message_frame("The camera stopped sending frames."))
                return
            faces = engine.detect(frame)
            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 * (1 / max(now - last, 1e-6))  # smoothed
            last = now
            for face in faces:
                top, right, bottom, left = face.box
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 0), 2)
                cv2.putText(frame, f"{right - left}px", (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
                for x, y in face.left_eye + face.right_eye:
                    cv2.circle(frame, (x, y), 1, (0, 255, 255), -1)
            status = f"{info.backend} {info.width}x{info.height}  |  {fps:4.1f} frames/s processed  |  faces: {len(faces)}"
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (0, 0, 0), -1)
            cv2.putText(frame, status, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            yield _jpeg_part(frame)
    except CameraUnavailable as error:
        yield _jpeg_part(_message_frame(str(error)))
    finally:
        # Runs when the browser leaves the page too, so the camera is always released.
        if source is not None:
            source.close()
        camera_in_use.release()


def _message_frame(text):
    import numpy as np

    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(frame, text, (20, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return frame


def _jpeg_part(frame):
    _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"


@bp.route("/stream")
@role_required("admin")
def stream():
    config = dict(current_app.config)
    return Response(_annotated_frames(config), mimetype="multipart/x-mixed-replace; boundary=frame")
