"""Test adapters for the camera and vision seams (DESIGN.md)."""

import time

import numpy as np

from faceid.vision import DetectedFace

OPEN_EYE = ((0, 5), (3, 2), (6, 2), (9, 5), (6, 8), (3, 8))  # Eye Aspect Ratio = 1.0


def face(left=100, width=120, encoding=None, sharpness=200.0):
    """A scripted face: a box, open eyes, and the encoding and sharpness the engine will report for it."""
    box = (100, left + width, 100 + width, left)
    return ScriptedFace(DetectedFace(box=box, left_eye=OPEN_EYE, right_eye=OPEN_EYE), encoding, sharpness)


def encoding(seed):
    """A repeatable 128-number encoding. Different seeds are far apart (distance about 1.4 for unit vectors)."""
    vector = np.random.default_rng(seed).normal(size=128)
    return vector / np.linalg.norm(vector)


def near(base, distance):
    """An encoding exactly `distance` away from `base`."""
    direction = np.random.default_rng(999).normal(size=128)
    direction -= direction.dot(base) * base  # perpendicular to base
    return base + distance * direction / np.linalg.norm(direction)


class ScriptedFace:
    def __init__(self, detected, encoding, sharpness):
        self.detected = detected
        self.encoding = encoding
        self.sharpness = sharpness


class ScriptedEngine:
    """Reports whatever faces the test last `show`ed, for every frame."""

    def __init__(self):
        self.faces = []
        self.encode_calls = 0

    def show(self, *faces):
        self.faces = list(faces)

    def _scripted(self, detected):
        return next(f for f in self.faces if f.detected == detected)

    def detect(self, frame):
        return [f.detected for f in self.faces]

    def encode(self, frame, detected):
        self.encode_calls += 1
        return self._scripted(detected).encoding

    def sharpness(self, frame, detected):
        return self._scripted(detected).sharpness


class StillCamera:
    """A camera that always returns the same black frame."""

    def __init__(self, *_args):
        self.closed = False

    def read(self):
        time.sleep(0.01)  # like a real camera, don't return frames in a tight loop
        return np.zeros((720, 1280, 3), dtype=np.uint8)

    def close(self):
        self.closed = True
