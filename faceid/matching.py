"""Comparing Face Encodings (pure, numpy only). Shared by Face Enrolment and live recognition."""

from typing import Hashable, NamedTuple

import numpy as np

Gallery = dict[Hashable, list[np.ndarray]]  # who (a student_id, or a display name) -> their Face Encodings


class Match(NamedTuple):
    who: Hashable
    distance: float


def face_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two Face Encodings, as in the synopsis."""
    return float(np.linalg.norm(a - b))


def nearest(encoding: np.ndarray, gallery: Gallery) -> Match | None:
    """The gallery entry closest to `encoding` and its Face Distance, or None for an empty gallery."""
    best = None
    for who, encodings in gallery.items():
        for known in encodings:
            distance = face_distance(encoding, known)
            if best is None or distance < best.distance:
                best = Match(who, distance)
    return best
