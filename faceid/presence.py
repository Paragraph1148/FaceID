"""Who is present in the camera's view (SPEC F4.2, F4.3, pure).

The PresenceTracker is fed one frame's detected faces at a time. It follows each face from frame to
frame by how much its box overlaps the previous one, so a face is encoded (about 0.1 s) only while it
is still being identified. A Student is confirmed when one followed face has matched them in the
Confirmation Frames number of consecutive frames, and a Blink has been seen on their face.

No clock, no camera, no dlib: the caller passes faces in and gets annotations and confirmations out.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from faceid.matching import Gallery, nearest
from faceid.vision import DetectedFace

MIN_OVERLAP = 0.3          # intersection over union for "the same face as last frame"
MAX_MISSED_FRAMES = 5      # a face undetected for longer is forgotten
UNKNOWN_RECHECK_FRAMES = 10  # an Unknown face is encoded again this often, in case it was a poor view


@dataclass(frozen=True)
class PresenceRules:
    tolerance: float
    confirmation_frames: int
    ear_threshold: float
    blink_frames: int


@dataclass(frozen=True)
class Annotation:
    """What to draw on one face: its box, who it is (None if Unknown) and its state."""

    box: tuple[int, int, int, int]
    student_id: int | None
    state: str  # "unknown", "waiting" (matched, not yet marked) or "marked"


@dataclass(frozen=True)
class Observation:
    annotations: list[Annotation]
    newly_confirmed: list[tuple[int, float]]  # (student_id, Face Distance of the confirming match)


def eye_aspect_ratio(eye: tuple[tuple[int, int], ...]) -> float:
    """Soukupová and Čech's EAR: eye height over width from the 6 eye landmarks. Falls towards 0 as the eye closes."""
    p = np.asarray(eye, dtype=float)
    vertical = np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])
    horizontal = np.linalg.norm(p[0] - p[3])
    return float(vertical / (2 * horizontal)) if horizontal else 0.0


def _overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Intersection over union of two (top, right, bottom, left) boxes."""
    top, right, bottom, left = max(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3])
    inter = max(0, right - left) * max(0, bottom - top)
    area = lambda box: (box[1] - box[3]) * (box[2] - box[0])
    union = area(a) + area(b) - inter
    return inter / union if union else 0.0


@dataclass
class _Track:
    """One face followed across frames."""

    box: tuple[int, int, int, int]
    candidate: int | None = None   # the Student it matched last
    streak: int = 0                # consecutive frames matching `candidate`
    identified: bool = False       # matched for the Confirmation Frames: no more encoding
    non_matches: int = 0           # consecutive frames matching nobody
    last_encoded: int = -1         # frame number of the last encoding
    distance: float = 0.0          # Face Distance of the latest match
    closed_frames: int = 0         # consecutive frames with eyes closed
    blinked: bool = False
    missed: int = 0                # consecutive frames not detected

    def is_unknown(self, rules: PresenceRules) -> bool:
        return self.non_matches >= rules.confirmation_frames


@dataclass
class PresenceTracker:
    gallery: Gallery                    # student_id -> Face Encodings of the Expected Students
    rules: PresenceRules
    already_marked: set[int] = field(default_factory=set)

    def __post_init__(self):
        self._confirmed = set(self.already_marked)
        self._blinked: set[int] = set()  # Students seen blinking during the session
        self._tracks: list[_Track] = []
        self._frame = 0

    def replace_gallery(self, gallery: Gallery) -> None:
        """Use new Face Encodings (F4.6). Faces not yet identified are checked again on the next frame."""
        self.gallery = gallery
        for track in self._tracks:
            if not track.identified:
                track.non_matches, track.last_encoded = 0, -1

    def observe(self, faces: list[DetectedFace], encode: Callable[[DetectedFace], np.ndarray]) -> Observation:
        """Take one frame's faces. `encode` is called only for faces still being identified."""
        self._frame += 1
        seen = self._follow(faces)
        newly_confirmed = []
        annotations = []
        for face, track in seen:
            self._update_blink(track, face)
            if not track.identified and self._due_for_encoding(track):
                self._identify(track, encode(face))
            if track.identified:
                if track.blinked:
                    self._blinked.add(track.candidate)
                if track.candidate in self._blinked and track.candidate not in self._confirmed:
                    self._confirmed.add(track.candidate)
                    newly_confirmed.append((track.candidate, track.distance))
            annotations.append(Annotation(track.box, track.candidate, self._state(track)))
        return Observation(annotations, newly_confirmed)

    def _follow(self, faces: list[DetectedFace]) -> list[tuple[DetectedFace, _Track]]:
        """Pair each face with last frame's most-overlapping track, or a new one. Unseen tracks age and are dropped."""
        pairs = sorted(
            ((_overlap(face.box, track.box), i, j) for i, face in enumerate(faces) for j, track in enumerate(self._tracks)),
            reverse=True,
        )
        face_track: dict[int, _Track] = {}
        used = set()
        for overlap, i, j in pairs:
            if overlap < MIN_OVERLAP:
                break
            if i not in face_track and j not in used:
                face_track[i] = self._tracks[j]
                used.add(j)
        for j, track in enumerate(self._tracks):
            if j not in used:
                track.missed += 1
                track.streak = 0  # Confirmation Frames must be consecutive
        self._tracks = [track for track in self._tracks if track.missed <= MAX_MISSED_FRAMES]
        seen = []
        for i, face in enumerate(faces):
            track = face_track.get(i)
            if track is None:
                track = _Track(face.box)
                self._tracks.append(track)
            track.box, track.missed = face.box, 0
            seen.append((face, track))
        return seen

    def _update_blink(self, track: _Track, face: DetectedFace) -> None:
        """A Blink: the eyes stay below the EAR threshold for the blink frame count, then open again."""
        ear = (eye_aspect_ratio(face.left_eye) + eye_aspect_ratio(face.right_eye)) / 2
        if ear < self.rules.ear_threshold:
            track.closed_frames += 1
            return
        if track.closed_frames >= self.rules.blink_frames:
            track.blinked = True
        track.closed_frames = 0

    def _due_for_encoding(self, track: _Track) -> bool:
        if not track.is_unknown(self.rules):
            return True
        return self._frame - track.last_encoded >= UNKNOWN_RECHECK_FRAMES

    def _identify(self, track: _Track, encoding: np.ndarray) -> None:
        track.last_encoded = self._frame
        match = nearest(encoding, self.gallery)
        if match is None or match.distance > self.rules.tolerance:
            track.candidate, track.streak = None, 0
            track.non_matches += 1
            return
        track.non_matches = 0
        track.streak = track.streak + 1 if match.who == track.candidate else 1
        track.candidate, track.distance = match.who, match.distance
        track.identified = track.streak >= self.rules.confirmation_frames

    def _state(self, track: _Track) -> str:
        if track.candidate is None:
            return "unknown"
        return "marked" if track.identified and track.candidate in self._confirmed else "waiting"
