"""The database side of live recognition (DESIGN: live). Recognition runs outside any web request,
so each call opens its own application context, and with it its own database connection."""

from datetime import datetime

from flask import Flask

from faceid.live import SessionSnapshot
from faceid.store import attendance, people, teaching


class AppLiveStore:
    def __init__(self, app: Flask):
        self._app = app

    def load(self, session_id: int) -> SessionSnapshot:
        with self._app.app_context():
            session = teaching.get_class_session(session_id)
            gallery, names = people.encodings_of_session(session_id)
            return SessionSnapshot(session["starts_at"], gallery, names, attendance.marked_students(session_id))

    def mark(self, session_id: int, student_id: int, status: str, minutes_late: int | None,
             confidence: float, marked_at: datetime) -> bool:
        with self._app.app_context():
            return attendance.mark_recognised(session_id, student_id, status, minutes_late, confidence, marked_at)
