"""Where frames come from (DESIGN: camera seam).

`WebcamSource` reads the server's webcam. A `VideoFileSource` for recorded clips joins it in v0.3.0.
"""

import sys
from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np

# DirectShow on Windows: Media Foundation (the default) can take minutes to open some webcams.
BACKEND = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
BACKEND_NAME = {cv2.CAP_DSHOW: "DirectShow", cv2.CAP_V4L2: "V4L2", cv2.CAP_ANY: "default"}[BACKEND]


class FrameSource(Protocol):
    """Anything that delivers frames: the webcam, or (in tests and evaluation) a still image or video file."""

    def read(self) -> np.ndarray | None: ...
    def close(self) -> None: ...


class CameraUnavailable(Exception):
    """The webcam could not be opened or stopped delivering frames."""


@dataclass
class CameraInfo:
    backend: str
    width: int
    height: int
    reported_fps: float


class WebcamSource:
    def __init__(self, index: int, width: int, height: int):
        self._capture = cv2.VideoCapture(index, BACKEND)
        if not self._capture.isOpened():
            raise CameraUnavailable(f"Camera {index} could not be opened (backend {BACKEND_NAME}).")
        self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def info(self) -> CameraInfo:
        return CameraInfo(
            backend=BACKEND_NAME,
            width=int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            reported_fps=self._capture.get(cv2.CAP_PROP_FPS),
        )

    def read(self) -> np.ndarray | None:
        """The next frame as a BGR array, or None if the camera returned nothing."""
        ok, frame = self._capture.read()
        return frame if ok else None

    def close(self) -> None:
        self._capture.release()
