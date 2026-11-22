"""Attendance rules (SPEC F5, pure): Present or Late, Attendance Credit, Attendance Percentage,
and what the Class Session and Manual Override forms accept.

Live marking, Manual Override and reports all call these, so each rule has one definition.
"""

from datetime import date, datetime, time, timedelta

STATUSES = ("present", "late", "absent")


def status_for(recognised_at: datetime, starts_at: datetime, late_threshold_minutes: int) -> tuple[str, int | None]:
    """("present", None) up to the Late Threshold after the start, otherwise ("late", whole minutes late)."""
    if recognised_at <= starts_at + timedelta(minutes=late_threshold_minutes):
        return "present", None
    return "late", int((recognised_at - starts_at).total_seconds() // 60)


def credit(status: str, minutes_late: int | None, session_minutes: int) -> float:
    """Attendance Credit (ADR 0005): 1 present, 0 absent, and for late the share of the session left after arriving."""
    if status == "present":
        return 1.0
    if status == "late":
        return max(0.0, (session_minutes - (minutes_late or 0)) / session_minutes)
    return 0.0


def percentage(credits: list[float], held_sessions: int) -> float | None:
    """Attendance Percentage over the held (not cancelled) Class Sessions; None when none were held."""
    if held_sessions == 0:
        return None
    return sum(credits) / held_sessions * 100


def suggested_times(now: datetime) -> tuple[time, time]:
    """Default start and end for a new Class Session: now, and an hour later."""
    start = now.replace(second=0, microsecond=0)
    end = min(start + timedelta(hours=1), start.replace(hour=23, minute=59))  # a Class Session ends on its own day
    return start.time(), end.time()


def minutes_between(start: time, end: time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


# --- Form rules ---


def _parse_time(text: str) -> time | None:
    try:
        return datetime.strptime(text.strip(), "%H:%M").time()
    except ValueError:
        return None


def clean_class_session(form: dict, subject_ids: set[int], today: date) -> tuple[dict, dict]:
    """F5.1: a Class Session starts today (creating it opens it, ADR 0007), for one of the Faculty's active Subjects."""
    errors = {}
    subject_id = int(form["subject_id"]) if str(form.get("subject_id", "")).isdigit() else None
    if subject_id not in subject_ids:
        errors["subject_id"] = "Choose one of your Subjects."
    start, end = _parse_time(form.get("start_time", "")), _parse_time(form.get("end_time", ""))
    for name, value in (("start_time", start), ("end_time", end)):
        if value is None:
            errors[name] = "Enter a time like 10:30."
    if start and end and end <= start:
        errors["end_time"] = "The end time must be after the start time."
    values = {
        "subject_id": subject_id,
        "session_date": today,
        "start_time": start,
        "end_time": end,
        "room_no": form.get("room_no", "").strip() or None,
    }
    return values, errors


def clean_override(form: dict, session_minutes: int) -> tuple[tuple[str, int | None] | None, str | None]:
    """F5.6: ((status, minutes_late), None) for a valid Manual Override, or (None, why not)."""
    status = form.get("status", "")
    if status not in STATUSES:
        return None, "Choose present, late or absent."
    if status != "late":
        return (status, None), None
    minutes = form.get("minutes_late", "").strip()
    if not minutes.isdigit() or not 1 <= int(minutes) <= session_minutes:
        return None, f"Enter how many minutes late, from 1 to {session_minutes}."
    return (status, int(minutes)), None
