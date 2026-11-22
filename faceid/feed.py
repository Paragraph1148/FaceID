"""Shares one webcam between pages (ADR 0004: one camera per server).

A background thread keeps the latest frame. The camera opens on first use and is released
after `idle_seconds` without anyone asking for a frame, so it isn't left on. When it is released,
the last frame is dropped too: frames live in memory only while the camera is in use (ADR 0002).
"""

import threading
import time
from collections.abc import Callable

import numpy as np

from faceid.camera import CameraUnavailable, FrameSource

FRESH_SECONDS = 1.0  # a frame older than this is never handed out, e.g. to a Capture


class CameraFeed:
    def __init__(
        self, open_source: Callable[[], FrameSource], idle_seconds: float = 15.0, first_frame_timeout: float = 10.0
    ):
        self._open_source = open_source
        self._idle_seconds = idle_seconds
        self._first_frame_timeout = first_frame_timeout
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame: tuple[float, np.ndarray] | None = None  # (time captured, frame)
        self._error: str | None = None
        self._last_request = 0.0

    def latest_frame(self) -> np.ndarray:
        """A copy of a frame captured within the last second. Opens the camera if needed.

        Raises CameraUnavailable if the camera can't be opened or sends nothing.
        """
        return self.next_frame(after=0.0)[1]

    def next_frame(self, after: float) -> tuple[float, np.ndarray]:
        """(capture time, copy of the frame) for a fresh frame captured later than `after`.

        Live recognition passes the time of the frame it processed last, so it never sees a frame twice.
        """
        with self._lock:
            self._last_request = time.monotonic()
            if self._thread is None or not self._thread.is_alive():
                self._frame, self._error = None, None
                self._stop.clear()
                self._thread = threading.Thread(target=self._run, name="camera-feed", daemon=True)
                self._thread.start()
        deadline = time.monotonic() + self._first_frame_timeout
        while time.monotonic() < deadline:
            latest, error = self._frame, self._error
            if error:
                raise CameraUnavailable(error)
            if latest is not None and latest[0] > after and time.monotonic() - latest[0] < FRESH_SECONDS:
                return latest[0], latest[1].copy()
            time.sleep(0.005)
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
                self._frame = (time.monotonic(), frame)
        finally:
            source.close()
            self._frame = None
