"""Live camera views for the browser (MJPEG).

`mjpeg_preview` serves the diagnostics and Face Enrolment pages: each face gets a box labelled with its width and sharpness, the two things Face Enrolment checks,
so the operator can see a problem before pressing Capture. `mjpeg_live` serves an open Class Session,
drawing the live recognition's latest boxes and names. Frames are only ever held in memory.
"""

import time
from collections.abc import Iterator

import cv2
import numpy as np

from faceid.camera import CameraUnavailable
from faceid.enrolment import EnrolmentRules
from faceid.feed import CameraFeed
from faceid.live import LiveSession
from faceid.vision import FaceEngine

GREEN, AMBER, YELLOW, WHITE, RED = (0, 200, 0), (0, 165, 255), (0, 255, 255), (255, 255, 255), (0, 0, 220)
MAX_FPS = 15  # the browser needs no more, and it leaves CPU for recognition
LIVE_MAX_FPS = 25  # N1 asks for a live view of at least 20 frames per second
STATE_COLOURS = {"unknown": RED, "waiting": AMBER, "marked": GREEN}


def mjpeg_preview(feed: CameraFeed, engine: FaceEngine, rules: EnrolmentRules) -> Iterator[bytes]:
    """Multipart MJPEG parts until the browser disconnects or the camera fails."""
    fps, last = 0.0, time.perf_counter()
    while True:
        try:
            frame = feed.latest_frame()
        except CameraUnavailable as error:
            yield _jpeg_part(_message_frame(str(error)))
            return
        faces = engine.detect(frame)
        for face in faces:
            top, right, bottom, left = face.box
            sharpness = engine.sharpness(frame, face)
            colour = GREEN if face.width >= rules.min_face_width and sharpness >= rules.min_sharpness else AMBER
            cv2.rectangle(frame, (left, top), (right, bottom), colour, 2)
            cv2.putText(frame, f"{face.width}px  sharp {sharpness:.0f}", (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
            for x, y in face.left_eye + face.right_eye:
                cv2.circle(frame, (x, y), 1, YELLOW, -1)
        elapsed = time.perf_counter() - last
        if elapsed < 1 / MAX_FPS:
            time.sleep(1 / MAX_FPS - elapsed)
        now = time.perf_counter()
        fps = 0.9 * fps + 0.1 / max(now - last, 1e-6)  # smoothed so the number is readable
        last = now
        _status_bar(frame, f"{frame.shape[1]}x{frame.shape[0]}  |  {fps:4.1f} frames/s processed  |  faces: {len(faces)}")
        yield _jpeg_part(frame)


def mjpeg_live(feed: CameraFeed, live: LiveSession, session_id: int) -> Iterator[bytes]:
    """The open Class Session's camera with each face's box and name, until the session stops recognising."""
    last = time.perf_counter()
    while live.session_id == session_id:
        try:
            frame = feed.latest_frame()
        except CameraUnavailable as error:
            yield _jpeg_part(_message_frame(str(error)))
            return
        for face in live.faces:
            top, right, bottom, left = face.box
            colour = STATE_COLOURS[face.state]
            cv2.rectangle(frame, (left, top), (right, bottom), colour, 2)
            cv2.putText(frame, face.label, (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
        _status_bar(frame, f"recognition {live.fps:4.1f} frames/s  |  faces: {len(live.faces)}")
        elapsed = time.perf_counter() - last
        if elapsed < 1 / LIVE_MAX_FPS:
            time.sleep(1 / LIVE_MAX_FPS - elapsed)
        last = time.perf_counter()
        yield _jpeg_part(frame)
    yield _jpeg_part(_message_frame("This Class Session is no longer open."))


def _status_bar(frame: np.ndarray, text: str) -> None:
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (0, 0, 0), -1)
    cv2.putText(frame, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, WHITE, 2)


def _message_frame(text: str) -> np.ndarray:
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(frame, text, (20, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 2)
    return frame


def _jpeg_part(frame: np.ndarray) -> bytes:
    _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
