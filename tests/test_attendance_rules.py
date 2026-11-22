"""F5.3, F5.6, F5.7: Present or Late, Attendance Credit and Attendance Percentage (faceid.attendance, pure)."""

from datetime import date, datetime, time

import pytest

from faceid.attendance import clean_class_session, clean_override, credit, percentage, status_for

START = datetime(2026, 12, 1, 10, 0)


@pytest.mark.parametrize(
    "recognised_at, expected",
    [
        (datetime(2026, 12, 1, 9, 55), ("present", None)),       # before the start
        (datetime(2026, 12, 1, 10, 10, 0), ("present", None)),   # exactly at the Late Threshold
        (datetime(2026, 12, 1, 10, 10, 1), ("late", 10)),        # just after it
        (datetime(2026, 12, 1, 10, 25, 59), ("late", 25)),       # whole minutes, rounded down
    ],
)
def test_recognition_after_the_late_threshold_is_late_with_the_minutes_late(recognised_at, expected):
    assert status_for(recognised_at, START, late_threshold_minutes=10) == expected


def test_credit_is_one_for_present_and_zero_for_absent():
    assert credit("present", None, session_minutes=60) == 1.0
    assert credit("absent", None, session_minutes=60) == 0.0


def test_late_credit_is_the_share_of_the_session_left_after_arriving():
    # ADR 0005's worked example: 15 minutes into a 60-minute session earns 0.75.
    assert credit("late", 15, session_minutes=60) == 0.75


def test_late_credit_never_goes_below_zero():
    assert credit("late", 90, session_minutes=60) == 0.0


def test_percentage_is_total_credit_over_held_sessions():
    assert percentage([1.0, 0.75, 0.0, 1.0], held_sessions=4) == 68.75


def test_percentage_with_no_held_sessions_is_none():
    assert percentage([], held_sessions=0) is None


# --- Form rules ---

TODAY = date(2026, 12, 1)


def session_form(**changes):
    form = {"subject_id": "3", "start_time": "10:00", "end_time": "11:00", "room_no": " 204 "}
    return {**form, **changes}


def test_a_valid_class_session_form_is_cleaned():
    values, errors = clean_class_session(session_form(), subject_ids={3, 4}, today=TODAY)

    assert errors == {}
    assert values == {"subject_id": 3, "session_date": TODAY, "start_time": time(10, 0), "end_time": time(11, 0), "room_no": "204"}


def test_an_empty_room_is_stored_as_none():
    values, _ = clean_class_session(session_form(room_no=""), subject_ids={3}, today=TODAY)

    assert values["room_no"] is None


def test_the_subject_must_be_one_of_the_faculty_members_active_subjects():
    _, errors = clean_class_session(session_form(subject_id="9"), subject_ids={3}, today=TODAY)

    assert errors == {"subject_id": "Choose one of your Subjects."}


def test_the_end_time_must_be_after_the_start_time():
    _, errors = clean_class_session(session_form(end_time="10:00"), subject_ids={3}, today=TODAY)

    assert errors == {"end_time": "The end time must be after the start time."}


def test_times_must_be_valid():
    _, errors = clean_class_session(session_form(start_time="25:00", end_time=""), subject_ids={3}, today=TODAY)

    assert errors == {"start_time": "Enter a time like 10:30.", "end_time": "Enter a time like 10:30."}


def test_an_override_to_present_or_absent_needs_no_minutes():
    assert clean_override({"status": "present", "minutes_late": "7"}, session_minutes=60) == (("present", None), None)
    assert clean_override({"status": "absent"}, session_minutes=60) == (("absent", None), None)


def test_an_override_to_late_needs_minutes_within_the_session():
    assert clean_override({"status": "late", "minutes_late": "15"}, session_minutes=60) == (("late", 15), None)
    assert clean_override({"status": "late", "minutes_late": ""}, session_minutes=60) == (
        None, "Enter how many minutes late, from 1 to 60.")
    assert clean_override({"status": "late", "minutes_late": "61"}, session_minutes=60) == (
        None, "Enter how many minutes late, from 1 to 60.")


def test_an_unknown_override_status_is_refused():
    assert clean_override({"status": "excused"}, session_minutes=60) == (None, "Choose present, late or absent.")
