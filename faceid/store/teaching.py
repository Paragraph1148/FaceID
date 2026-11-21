"""Subjects and Class Sessions (SPEC F2, F5)."""

from faceid.store import db


def list_subjects():
    return db.query(
        "SELECT s.subject_id, s.subject_code, s.subject_name, s.course, s.semester, s.is_active,"
        " f.name AS faculty_name FROM subject s JOIN faculty f ON f.faculty_id = s.faculty_id"
        " ORDER BY s.is_active DESC, s.course, s.semester, s.subject_code"
    )


def get_subject(subject_id):
    return db.query_one("SELECT * FROM subject WHERE subject_id = %s", (subject_id,))


def create_subject(subject_code, subject_name, course, semester, faculty_id):
    return db.execute(
        "INSERT INTO subject (subject_code, subject_name, course, semester, faculty_id) VALUES (%s, %s, %s, %s, %s)",
        (subject_code, subject_name, course, semester, faculty_id),
    )


def update_subject(subject_id, subject_code, subject_name, course, semester, faculty_id):
    db.execute(
        "UPDATE subject SET subject_code = %s, subject_name = %s, course = %s, semester = %s, faculty_id = %s"
        " WHERE subject_id = %s",
        (subject_code, subject_name, course, semester, faculty_id, subject_id),
    )


def set_subject_active(subject_id, active):
    db.execute("UPDATE subject SET is_active = %s WHERE subject_id = %s", (active, subject_id))
