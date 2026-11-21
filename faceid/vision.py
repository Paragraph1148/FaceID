"""The face engine (DESIGN: vision seam). The only module that imports face_recognition or dlib."""

from dataclasses import dataclass

import cv2
import dlib
import face_recognition
import numpy as np


@dataclass(frozen=True)
class DetectedFace:
    """One face in a frame. `box` is (top, right, bottom, left) in full-frame pixels."""

    box: tuple[int, int, int, int]
    left_eye: tuple[tuple[int, int], ...]   # 6 landmark points, as used by the Eye Aspect Ratio
    right_eye: tuple[tuple[int, int], ...]


def engine_description() -> str:
    """Version and GPU support of the face engine, for the diagnostics page."""
    return f"dlib {dlib.__version__} (CUDA: {'yes' if dlib.DLIB_USE_CUDA else 'no'})"


class DlibEngine:
    def __init__(self, detector: str = "hog", scale: float = 1.0, upsample: int = 0):
        self.detector = detector
        self.scale = scale
        self.upsample = upsample

    def detect(self, frame_bgr: np.ndarray) -> list[DetectedFace]:
        """Find faces and their eye landmarks in an OpenCV (BGR) frame. Cheap compared with encoding."""
        image = frame_bgr if self.scale == 1.0 else cv2.resize(frame_bgr, (0, 0), fx=self.scale, fy=self.scale)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
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
