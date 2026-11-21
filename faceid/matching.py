"""Comparing Face Encodings (pure, numpy only). Shared by Face Enrolment and live recognition."""

import numpy as np

Gallery = dict[object, list[np.ndarray]]  # who (e.g. a student_id or a display name) -> their Face Encodings


def face_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two Face Encodings, as in the synopsis."""
    return float(np.linalg.norm(a - b))


def nearest(encoding: np.ndarray, gallery: Gallery) -> tuple[object, float] | None:
    """The gallery entry closest to `encoding` and its Face Distance, or None for an empty gallery."""
    best = None
    for who, encodings in gallery.items():
        for known in encodings:
            distance = face_distance(encoding, known)
            if best is None or distance < best[1]:
                best = (who, distance)
    return best
