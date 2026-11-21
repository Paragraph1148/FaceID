"""Camera diagnostics (SPEC §8, v0.1.0): proves the webcam and dlib work on this machine.

Produces annotated JPEG frames: HOG face boxes with their width in pixels, eye landmarks,
and the processing speed. Frames are only ever held in memory.
"""

import threading
import time
from collections.abc import Iterator

import cv2
import numpy as np

from faceid.camera import CameraUnavailable, WebcamSource
from faceid.vision import DetectedFace, DlibEngine

# One camera, so one viewer at a time.
camera_in_use = threading.Lock()


def mjpeg_frames(config: dict) -> Iterator[bytes]:
    """Multipart MJPEG parts for the browser, until the client disconnects or the camera fails."""
    if not camera_in_use.acquire(blocking=False):
        yield _jpeg_part(_message_frame("Camera is in use by another page or session."))
        return
    source = None
    try:
        source = WebcamSource(config["CAMERA_INDEX"], config["CAMERA_WIDTH"], config["CAMERA_HEIGHT"])
        info = source.info()
        engine = DlibEngine(config["DETECTOR"], config["DETECTION_SCALE"], config["DETECTION_UPSAMPLE"])
        fps, last = 0.0, time.perf_counter()
        while True:
            frame = source.read()
            if frame is None:
                yield _jpeg_part(_message_frame("The camera stopped sending frames."))
                return
            faces = engine.detect(frame)
            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 / max(now - last, 1e-6)  # smoothed so the number is readable
            last = now
            _draw(frame, faces, f"{info.backend} {info.width}x{info.height}  |  {fps:4.1f} frames/s processed  |  faces: {len(faces)}")
            yield _jpeg_part(frame)
    except CameraUnavailable as error:
        yield _jpeg_part(_message_frame(str(error)))
    finally:
        # Also runs when the browser leaves the page, so the camera is always released.
        if source is not None:
            source.close()
        camera_in_use.release()


def _draw(frame: np.ndarray, faces: list[DetectedFace], status: str) -> None:
    for face in faces:
        top, right, bottom, left = face.box
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 0), 2)
        cv2.putText(frame, f"{right - left}px", (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
        for x, y in face.left_eye + face.right_eye:
            cv2.circle(frame, (x, y), 1, (0, 255, 255), -1)
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (0, 0, 0), -1)
    cv2.putText(frame, status, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)


def _message_frame(text: str) -> np.ndarray:
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(frame, text, (20, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return frame


def _jpeg_part(frame: np.ndarray) -> bytes:
    _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
