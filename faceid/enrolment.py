"""Face Enrolment rules (SPEC F3, pure): is this Capture acceptable, and which poses are still needed.

Works on the face engine's output only. It never stores or returns an image.
"""

from dataclasses import dataclass, field

import numpy as np

from faceid.matching import Gallery, nearest

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


@dataclass(frozen=True)
class Accepted:
    encoding: np.ndarray

    def __eq__(self, other):
        return isinstance(other, Accepted) and bool((self.encoding == other.encoding).all())


@dataclass(frozen=True)
class Rejected:
    reason: str


def assess_capture(frame, engine, others: Gallery, rules: EnrolmentRules) -> Accepted | Rejected:
    """Accept a Capture only if it shows exactly one large, sharp face that isn't another enrolled Student.

    `others` maps each other Student's display name to their Face Encodings.
    Cheap checks run first, because encoding takes about 0.1 s.
    """
    faces = engine.detect(frame)
    if not faces:
        return Rejected("No face found. Look at the camera, in good light.")
    if len(faces) > 1:
        return Rejected(f"{len(faces)} faces in view. Only the Student being enrolled may be in front of the camera.")
    face = faces[0]
    top, right, bottom, left = face.box
    if right - left < rules.min_face_width:
        return Rejected(f"Face is too small ({right - left} px, needs {rules.min_face_width}). Move closer to the camera.")
    if engine.sharpness(frame, face) < rules.min_sharpness:
        return Rejected("The picture is blurred. Hold still and try again.")
    encoding = engine.encode(frame, face)
    match = nearest(encoding, others)
    if match and match[1] <= rules.tolerance:
        return Rejected(f"This face matches {match[0]}, who is already enrolled.")
    return Accepted(encoding)


@dataclass
class EnrolmentDraft:
    """The Face Encodings captured so far for one Student, one per pose. Held in memory until saved."""

    student_id: int
    captured: dict[str, np.ndarray] = field(default_factory=dict)

    def accept(self, pose: str, encoding: np.ndarray) -> None:
        if pose not in POSES:
            raise ValueError(f"unknown pose {pose!r}")
        self.captured[pose] = encoding  # capturing a pose again replaces it

    def missing(self) -> list[str]:
        return [pose for pose in POSES if pose not in self.captured]

    def encodings(self) -> list[np.ndarray]:
        """All five encodings, in pose order. Only valid once nothing is missing."""
        if self.missing():
            raise ValueError("enrolment is incomplete")
        return [self.captured[pose] for pose in POSES]
