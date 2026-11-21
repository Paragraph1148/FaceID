"""The real face engine (DlibEngine) on public-domain portraits (tests/fixtures/faces/README.md)."""

from pathlib import Path

import cv2
import pytest

from faceid.matching import face_distance
from faceid.vision import DlibEngine

FACES = Path(__file__).parent / "fixtures" / "faces"


@pytest.fixture(scope="module")
def engine():
    return DlibEngine()


def photo(name):
    return cv2.imread(str(FACES / f"{name}.jpg"))


def only_face(engine, frame):
    faces = engine.detect(frame)
    assert len(faces) == 1
    return faces[0]


def test_detects_one_face_with_six_point_eyes(engine):
    face = only_face(engine, photo("obama_2012"))

    top, right, bottom, left = face.box
    assert right - left > 80
    assert len(face.left_eye) == 6 and len(face.right_eye) == 6


def test_encodes_a_face_as_128_numbers(engine):
    frame = photo("biden_2021")

    encoding = engine.encode(frame, only_face(engine, frame))

    assert encoding.shape == (128,)


def test_same_person_is_within_tolerance_and_different_people_are_not(engine):
    def encode(name):
        frame = photo(name)
        return engine.encode(frame, only_face(engine, frame))

    biden_2013, biden_2021, obama = encode("biden_2013"), encode("biden_2021"), encode("obama_2012")

    assert face_distance(biden_2013, biden_2021) < 0.6
    assert face_distance(obama, biden_2021) > 0.6


def test_blurring_lowers_sharpness(engine):
    frame = photo("obama_2012")
    blurred = cv2.GaussianBlur(frame, (15, 15), 0)
    face = only_face(engine, frame)

    assert engine.sharpness(blurred, face) < engine.sharpness(frame, face) / 5


def test_scaled_detection_reports_boxes_in_full_frame_pixels(engine):
    frame = cv2.resize(photo("obama_2012"), (0, 0), fx=2, fy=2)
    full = only_face(DlibEngine(scale=1.0), frame)
    half = only_face(DlibEngine(scale=0.5), frame)

    width = full.box[1] - full.box[3]
    # HOG snaps boxes to its grid, so they differ a little; unscaled coordinates would be off by half the frame.
    assert all(abs(a - b) < 0.1 * width for a, b in zip(full.box, half.box))
