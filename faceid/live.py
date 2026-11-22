"""The running Class Session (DESIGN: live): recognition on its own thread while a session is open.

The camera feed's thread captures frames. This module's thread takes each new frame through
`engine.detect` -> `PresenceTracker.observe` (which encodes only faces still being identified), and
marks each newly confirmed Student with `attendance.status_for`. The browser's live view draws the
latest annotations on the latest frame, so it stays smooth even when recognition is slower.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import numpy as np

from faceid.attendance import status_for
from faceid.camera import CameraUnavailable
from faceid.feed import CameraFeed
from faceid.presence import PresenceRules, PresenceTracker
from faceid.vision import FaceEngine

log = logging.getLogger(__name__)
RETRY_SECONDS = 1.0  # wait after a camera or database error before trying again
SAVE_FAILED = "A mark could not be saved and is being retried. See the server log."


@dataclass(frozen=True)
class SessionSnapshot:
    """What recognition needs from the database about one open Class Session."""

    starts_at: datetime
    gallery: dict[int, list[np.ndarray]]  # Expected Students with Face Encodings
    names: dict[int, str]                 # every Expected Student
    already_marked: set[int]


class LiveStore(Protocol):
    def load(self, session_id: int) -> SessionSnapshot: ...
    def mark(self, session_id: int, student_id: int, status: str, minutes_late: int | None,
             confidence: float, marked_at: datetime) -> bool: ...


@dataclass(frozen=True)
class LabelledFace:
    box: tuple[int, int, int, int]
    state: str   # "unknown", "waiting" or "marked"
    label: str


class LiveSession:
    """Recognition for the server's one open Class Session (ADR 0004: one camera)."""

    def __init__(self, feed: CameraFeed, engine: FaceEngine, store: LiveStore, rules: PresenceRules,
                 late_threshold_minutes: int, clock: Callable[[], datetime] = datetime.now):
        self._feed, self._engine, self._store = feed, engine, store
        self._rules, self._late_threshold, self._clock = rules, late_threshold_minutes, clock
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._reload = threading.Event()
        self.session_id: int | None = None
        self.faces: list[LabelledFace] = []
        self.fps = 0.0
        self.error: str | None = None

    def ensure_running(self, session_id: int) -> None:
        """Start recognising for `session_id`, unless that is already happening."""
        with self._lock:
            if self.session_id == session_id and self._is_alive():
                return
            self._stop_thread()
            self.session_id, self.faces, self.fps, self.error = session_id, [], 0.0, None
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(session_id, self._stop), name="recognition", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop recognising (the session was closed or cancelled, or the server is stopping)."""
        with self._lock:
            self._stop_thread()
            self.session_id, self.faces = None, []

    def stop_if(self, session_id: int) -> None:
        """Stop recognising, if it is for `session_id`."""
        if self.session_id == session_id:
            self.stop()

    def report(self, session_id: int) -> dict:
        """For the session page: is the camera recognising for this session, how fast, and any problem."""
        if self.session_id != session_id:
            return {"recognising": False, "fps": None, "error": None}
        return {"recognising": self._is_alive(), "fps": round(self.fps, 1), "error": self.error}

    def enrolment_changed(self) -> None:
        """Face Enrolment changed: reload the Expected Students' encodings before the next frame (F4.6)."""
        self._reload.set()

    def _is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _stop_thread(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    def _run(self, session_id: int, stop: threading.Event) -> None:
        snapshot = tracker = None
        last_frame_at = 0.0
        while not stop.is_set():
            try:
                if tracker is None or self._reload.is_set():
                    self._reload.clear()
                    snapshot = self._store.load(session_id)
                    if snapshot.starts_at.date() != self._clock().date():
                        # Marking now would make everyone hours late; the Faculty should close it instead.
                        self.error = (f"This Class Session began on {snapshot.starts_at:%d %b %Y}, so the camera "
                                      "won't mark anyone for it. Close it, then start a new one.")
                        return
                    if tracker is None:
                        tracker = PresenceTracker(snapshot.gallery, self._rules, set(snapshot.already_marked))
                    else:
                        tracker.replace_gallery(snapshot.gallery)
                started = time.perf_counter()
                last_frame_at, frame = self._feed.next_frame(after=last_frame_at, cancel=stop)
                faces = self._engine.detect(frame)
                result = tracker.observe(faces, lambda face: self._engine.encode(frame, face))
                saved = [self._mark(session_id, snapshot, tracker, student_id, distance)
                         for student_id, distance in result.newly_confirmed]
                labelled = [LabelledFace(a.box, a.state, _label(a.state, snapshot.names.get(a.student_id))) for a in result.annotations]
                fps = 0.8 * self.fps + 0.2 / max(time.perf_counter() - started, 1e-6)
                self._publish(stop, labelled, fps, None if all(saved) else SAVE_FAILED)
            except CameraUnavailable as error:
                self._publish(stop, [], self.fps, str(error))
                stop.wait(RETRY_SECONDS)
            except Exception:  # a database hiccup must not end recognition for the rest of the class
                log.exception("live recognition failed; retrying")
                self._publish(stop, self.faces, self.fps, "Recognition hit an error and is retrying. See the server log.")
                stop.wait(RETRY_SECONDS)

    def _publish(self, stop: threading.Event, faces: list[LabelledFace], fps: float, error: str | None) -> None:
        """Show this thread's results, unless it has been stopped: a stopped thread must not overwrite the next one's."""
        if not stop.is_set():
            self.faces, self.fps, self.error = faces, fps, error

    def _mark(self, session_id: int, snapshot: SessionSnapshot, tracker: PresenceTracker, student_id: int, distance: float) -> bool:
        """Save one confirmed Student's mark. False if saving failed, in which case it is retried later."""
        now = self._clock()
        status, minutes_late = status_for(now, snapshot.starts_at, self._late_threshold)
        try:
            # Match Confidence = 1 - Face Distance (F5.3)
            self._store.mark(session_id, student_id, status, minutes_late, round(1 - distance, 4), now)
        except Exception:
            log.exception("could not save a mark; it will be retried")
            tracker.unconfirm(student_id)  # confirm and save again on a later frame
            return False
        return True


def _label(state: str, name: str | None) -> str:
    if state == "unknown" or name is None:
        return "Unknown"
    return f"{name}: marked" if state == "marked" else f"{name}: blink to confirm"
