"""Face Enrolment rules (SPEC F3, pure): is this Capture acceptable, which poses are still needed,
and may the result be saved.

Works on the face engine's output only. It never stores or returns an image.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Hashable

import numpy as np

from faceid.matching import Gallery, nearest
from faceid.vision import FaceEngine

# Guidance only: the head angle itself isn't checked (SPEC §9).
POSES = {
    "front": "Look straight at the camera",
    "left": "Turn your head a little to your left",
    "right": "Turn your head a little to your right",
    "up": "Lift your chin a little",
    "down": "Lower your chin a little",
}


@dataclass(frozen=True)
class EnrolmentRules:
    min_face_width: int
    min_sharpness: float
    tolerance: float


@dataclass(frozen=True, eq=False)
class Accepted:
    encoding: np.ndarray


@dataclass(frozen=True)
class Rejected:
    reason: str


def _already_enrolled(encoding: np.ndarray, others: Gallery, tolerance: float) -> Rejected | None:
    match = nearest(encoding, others)
    if match and match.distance <= tolerance:
        return Rejected(f"This face matches {match.who}, who is already enrolled.")
    return None


def assess_capture(frame: np.ndarray, engine: FaceEngine, others: Gallery, rules: EnrolmentRules) -> Accepted | Rejected:
    """Accept a Capture only if it shows exactly one large, sharp face that isn't another enrolled Student.

    `others` maps each other active Student's display name to their Face Encodings.
    Cheap checks run first, because encoding takes about 0.1 s.
    """
    faces = engine.detect(frame)
    if not faces:
        return Rejected("No face found. Look at the camera, in good light.")
    if len(faces) > 1:
        return Rejected(f"{len(faces)} faces in view. Only the Student being enrolled may be in front of the camera.")
    face = faces[0]
    if face.width < rules.min_face_width:
        return Rejected(f"Face is too small ({face.width} px, needs {rules.min_face_width}). Move closer to the camera.")
    if engine.sharpness(frame, face) < rules.min_sharpness:
        return Rejected("The picture is blurred. Hold still and try again.")
    encoding = engine.encode(frame, face)
    return _already_enrolled(encoding, others, rules.tolerance) or Accepted(encoding)


@dataclass
class EnrolmentDraft:
    """The Face Encodings captured so far for one Student, one per pose. Held in memory until saved."""

    student_id: int
    captured: dict[str, np.ndarray] = field(default_factory=dict)
    touched: float = field(default_factory=time.monotonic)

    def missing(self) -> list[str]:
        return [pose for pose in POSES if pose not in self.captured]

    def capture(self, pose: str, frame: np.ndarray, engine: FaceEngine, others: Gallery, rules: EnrolmentRules) -> Accepted | Rejected:
        """Assess one Capture for `pose` and keep its encoding if accepted. Capturing a pose again replaces it."""
        if pose not in POSES:
            raise ValueError(f"unknown pose {pose!r}")
        result = assess_capture(frame, engine, others, rules)
        if isinstance(result, Accepted):
            self.captured[pose] = result.encoding
        self.touched = time.monotonic()
        return result

    def ready_to_save(self, others: Gallery, rules: EnrolmentRules) -> list[np.ndarray] | Rejected:
        """The five encodings in pose order, or why they can't be saved.

        Other Students may have been enrolled since the Captures, so they are checked again.
        """
        if self.missing():
            return Rejected(f"Capture all {len(POSES)} poses first.")
        encodings = [self.captured[pose] for pose in POSES]
        for encoding in encodings:
            clash = _already_enrolled(encoding, others, rules.tolerance)
            if clash:
                return clash
        return encodings


class DraftStore:
    """Enrolment drafts, one per (owner, Student), shared by Flask's threads.

    The owner is one browser login, so two Admins (or two people) never mix Captures.
    Drafts left untouched for `max_age_seconds` are forgotten.
    """

    def __init__(self, max_age_seconds: float = 30 * 60):
        self._max_age = max_age_seconds
        self._drafts: dict[tuple[Hashable, int], EnrolmentDraft] = {}
        self._lock = threading.Lock()

    def get(self, owner: Hashable, student_id: int) -> EnrolmentDraft:
        """The owner's draft for this Student, starting an empty one if there is none."""
        with self._lock:
            self._forget_old()
            return self._drafts.setdefault((owner, student_id), EnrolmentDraft(student_id))

    def discard(self, owner: Hashable, student_id: int) -> None:
        with self._lock:
            self._drafts.pop((owner, student_id), None)

    def _forget_old(self) -> None:
        now = time.monotonic()
        for key in [key for key, draft in self._drafts.items() if now - draft.touched > self._max_age]:
            del self._drafts[key]
