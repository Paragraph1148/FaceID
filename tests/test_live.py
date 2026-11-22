"""LiveSession (DESIGN: live) with a store that fails, and stopping (N1: threads stop cleanly)."""

import time
from datetime import datetime

from conftest import wait_until
from fakes import CLOSED_EYE, ScriptedEngine, StillCamera, encoding, face

from faceid.feed import CameraFeed
from faceid.live import LiveSession, SessionSnapshot
from faceid.presence import PresenceRules

RULES = PresenceRules(tolerance=0.6, confirmation_frames=3, ear_threshold=0.25, blink_frames=1)
TODAY_10AM = datetime(2026, 12, 1, 10, 0)


class FlakyStore:
    """Asha is expected. The first `failures` marks raise, as a lost database connection would."""

    def __init__(self, failures=0, starts_at=TODAY_10AM):
        self.failures, self.starts_at, self.marks = failures, starts_at, []

    def load(self, session_id):
        return SessionSnapshot(self.starts_at, {1: [encoding(1)]}, {1: "Asha Verma"}, set())

    def mark(self, session_id, student_id, status, minutes_late, confidence, marked_at):
        if self.failures:
            self.failures -= 1
            raise ConnectionError("database went away")
        self.marks.append((student_id, status))
        return True


def live_with(store, engine):
    feed = CameraFeed(StillCamera)
    return LiveSession(feed, engine, store, RULES, 10, clock=lambda: TODAY_10AM), feed


def blink(engine):
    engine.show(face(encoding=encoding(1)))
    time.sleep(0.15)
    engine.show(face(encoding=encoding(1), eyes=CLOSED_EYE))
    time.sleep(0.15)
    engine.show(face(encoding=encoding(1)))


def test_a_mark_that_fails_to_save_is_saved_on_a_later_frame():
    store, engine = FlakyStore(failures=1), ScriptedEngine()
    live, feed = live_with(store, engine)
    live.ensure_running(1)

    blink(engine)

    wait_until(lambda: store.marks == [(1, "present")])
    live.stop(), feed.stop()


def test_stopping_ends_recognition_quickly_and_clears_the_faces():
    store, engine = FlakyStore(), ScriptedEngine()
    live, feed = live_with(store, engine)
    engine.show(face(encoding=encoding(1)))
    live.ensure_running(1)
    wait_until(lambda: live.faces)

    started = time.monotonic()
    live.stop()

    assert time.monotonic() - started < 1
    assert live.faces == [] and live.report(1)["recognising"] is False
    time.sleep(0.1)
    assert live.faces == []
    feed.stop()


def test_a_class_session_from_an_earlier_day_is_not_resumed():
    store, engine = FlakyStore(starts_at=datetime(2026, 11, 30, 10, 0)), ScriptedEngine()
    live, feed = live_with(store, engine)

    live.ensure_running(1)

    wait_until(lambda: live.report(1)["error"] is not None)
    assert "began on 30 Nov 2026" in live.report(1)["error"]
    assert live.report(1)["recognising"] is False
    live.stop(), feed.stop()
