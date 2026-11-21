"""Shares one webcam between pages (ADR 0004: one camera per server).

A background thread keeps the latest frame. The camera opens on first use and is released
after `idle_seconds` without anyone asking for a frame, so it isn't left on.
"""

import threading
import time
from collections.abc import Callable

import numpy as np

from faceid.camera import CameraUnavailable


class CameraFeed:
    def __init__(self, open_source: Callable[[], object], idle_seconds: float = 15.0, first_frame_timeout: float = 10.0):
        self._open_source = open_source
        self._idle_seconds = idle_seconds
        self._first_frame_timeout = first_frame_timeout
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame: np.ndarray | None = None
        self._error: str | None = None
        self._last_request = 0.0

    def latest_frame(self) -> np.ndarray:
        """The newest camera frame (a copy). Opens the camera if needed; raises CameraUnavailable on failure."""
        with self._lock:
            self._last_request = time.monotonic()
            if self._thread is None or not self._thread.is_alive():
                self._frame, self._error = None, None
                self._stop.clear()
                self._thread = threading.Thread(target=self._run, name="camera-feed", daemon=True)
                self._thread.start()
        deadline = time.monotonic() + self._first_frame_timeout
        while time.monotonic() < deadline:
            frame, error = self._frame, self._error
            if error:
                raise CameraUnavailable(error)
            if frame is not None:
                return frame.copy()
            time.sleep(0.01)
        raise CameraUnavailable(f"The camera sent no picture within {self._first_frame_timeout:.0f} seconds.")

    def stop(self) -> None:
        """Release the camera now (used when the server shuts down and by tests)."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        try:
            source = self._open_source()
        except CameraUnavailable as error:
            self._error = str(error)
            return
        try:
            while not self._stop.is_set() and time.monotonic() - self._last_request < self._idle_seconds:
                frame = source.read()
                if frame is None:
                    self._error = "The camera stopped sending frames."
                    return
                self._frame = frame
        finally:
            source.close()
