"""The face engine (DESIGN: vision seam). The only module that imports face_recognition or dlib."""

import threading
from dataclasses import dataclass
from typing import Protocol

import cv2
import dlib
import face_recognition
import numpy as np


SHARPNESS_WIDTH = 160  # px; the face is resized to this width before measuring sharpness


@dataclass(frozen=True)
class DetectedFace:
    """One face in a frame. `box` is (top, right, bottom, left) in full-frame pixels."""

    box: tuple[int, int, int, int]
    left_eye: tuple[tuple[int, int], ...]   # 6 landmark points, as used by the Eye Aspect Ratio
    right_eye: tuple[tuple[int, int], ...]

    @property
    def width(self) -> int:
        top, right, bottom, left = self.box
        return right - left


class FaceEngine(Protocol):
    """What the rest of FaceID needs from a face engine. `DlibEngine` is the real one; tests use a scripted one."""

    def detect(self, frame_bgr: np.ndarray) -> list[DetectedFace]: ...
    def sharpness(self, frame_bgr: np.ndarray, face: DetectedFace) -> float: ...
    def encode(self, frame_bgr: np.ndarray, face: DetectedFace) -> np.ndarray: ...


def engine_description() -> str:
    """Version and GPU support of the face engine, for the diagnostics page."""
    return f"dlib {dlib.__version__} (CUDA: {'yes' if dlib.DLIB_USE_CUDA else 'no'})"


class DlibEngine:
    """The real engine. Flask serves pages on several threads, so calls into dlib take turns."""

    def __init__(self, detector: str = "hog", scale: float = 1.0, upsample: int = 0):
        self.detector = detector
        self.scale = scale
        self.upsample = upsample
        self._dlib_lock = threading.Lock()  # dlib's models are not documented as safe for concurrent use

    def detect(self, frame_bgr: np.ndarray) -> list[DetectedFace]:
        """Find faces and their eye landmarks in an OpenCV (BGR) frame. Cheap compared with encoding."""
        image = frame_bgr if self.scale == 1.0 else cv2.resize(frame_bgr, (0, 0), fx=self.scale, fy=self.scale)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        with self._dlib_lock:
            boxes = face_recognition.face_locations(rgb, number_of_times_to_upsample=self.upsample, model=self.detector)
            landmarks = face_recognition.face_landmarks(rgb, boxes)
        return [
            DetectedFace(
                box=tuple(int(v / self.scale) for v in box),
                left_eye=tuple((int(x / self.scale), int(y / self.scale)) for x, y in marks["left_eye"]),
                right_eye=tuple((int(x / self.scale), int(y / self.scale)) for x, y in marks["right_eye"]),
            )
            for box, marks in zip(boxes, landmarks)
        ]

    def encode(self, frame_bgr: np.ndarray, face: DetectedFace) -> np.ndarray:
        """The 128-number Face Encoding of one detected face, computed at full resolution. About 0.1 s."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        with self._dlib_lock:
            encoding = face_recognition.face_encodings(rgb, [face.box])[0]
        return np.asarray(encoding, dtype=np.float64)

    def sharpness(self, frame_bgr: np.ndarray, face: DetectedFace) -> float:
        """Variance of the Laplacian over the face, resized to a fixed width so faces of any size compare fairly."""
        top, right, bottom, left = face.box
        height, width = frame_bgr.shape[:2]
        crop = frame_bgr[max(top, 0):min(bottom, height), max(left, 0):min(right, width)]
        if crop.size == 0:
            return 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (SHARPNESS_WIDTH, max(1, round(gray.shape[0] * SHARPNESS_WIDTH / gray.shape[1]))))
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
