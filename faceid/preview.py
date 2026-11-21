"""Live camera preview for the browser (MJPEG), used by the diagnostics and Face Enrolment pages.

Each face gets a box labelled with its width and sharpness, the two things Face Enrolment checks,
so the operator can see a problem before pressing Capture. Frames are only ever held in memory.
"""

import time
from collections.abc import Iterator

import cv2
import numpy as np

from faceid.camera import CameraUnavailable
from faceid.feed import CameraFeed

GREEN, AMBER, YELLOW, WHITE = (0, 200, 0), (0, 165, 255), (0, 255, 255), (255, 255, 255)


def mjpeg_preview(feed: CameraFeed, engine, min_face_width: int, min_sharpness: float) -> Iterator[bytes]:
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
            width, sharpness = right - left, engine.sharpness(frame, face)
            colour = GREEN if width >= min_face_width and sharpness >= min_sharpness else AMBER
            cv2.rectangle(frame, (left, top), (right, bottom), colour, 2)
            cv2.putText(frame, f"{width}px  sharp {sharpness:.0f}", (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
            for x, y in face.left_eye + face.right_eye:
                cv2.circle(frame, (x, y), 1, YELLOW, -1)
        now = time.perf_counter()
        fps = 0.9 * fps + 0.1 / max(now - last, 1e-6)  # smoothed so the number is readable
        last = now
        _status_bar(frame, f"{frame.shape[1]}x{frame.shape[0]}  |  {fps:4.1f} frames/s processed  |  faces: {len(faces)}")
        yield _jpeg_part(frame)


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
