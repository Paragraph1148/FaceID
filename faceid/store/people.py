"""Admin, Faculty and Student rows (SPEC F1, F2).

Password hashes never leave this module except through `find_login` and `get_account`, which login needs.
"""

import numpy as np

from faceid.passwords import hash_password
from faceid.store import db

ROLE_TABLES = {
    "admin": ("admin", "admin_id"),
    "faculty": ("faculty", "faculty_id"),
    "student": ("student", "student_id"),
}

# Each query returns one account's login fields under the same names, so login code treats all roles alike.
_LOGIN_BY_IDENTIFIER = {
    "admin": "SELECT admin_id AS id, username AS name, password_hash, FALSE AS must_change_password"
    " FROM admin WHERE email = %s",
    "faculty": "SELECT faculty_id AS id, name, password_hash, must_change_password"
    " FROM faculty WHERE email = %s AND is_active",
    "student": "SELECT student_id AS id, name, password_hash, must_change_password"
    " FROM student WHERE enrollment_no = %s AND is_active",
}
_LOGIN_BY_ID = {
    "admin": "SELECT admin_id AS id, username AS name, password_hash, FALSE AS must_change_password"
    " FROM admin WHERE admin_id = %s",
    "faculty": "SELECT faculty_id AS id, name, password_hash, must_change_password"
    " FROM faculty WHERE faculty_id = %s AND is_active",
    "student": "SELECT student_id AS id, name, password_hash, must_change_password"
    " FROM student WHERE student_id = %s AND is_active",
}

STUDENT_FIELDS = "student_id, enrollment_no, name, email, mobile, course, semester, section, is_active"
FACULTY_FIELDS = "faculty_id, name, email, department, is_active"


# --- Login (F1) ---


def find_login(identifier: str) -> tuple[str, dict] | None:
    """The account a login identifier refers to, as (role, row), or None.

    Admin and Faculty log in with their email address, Students with their Enrolment Number
    (stored in capitals, so any case works). Inactive Faculty and Students cannot log in.
    """
    for role, identifier_value in (("admin", identifier), ("faculty", identifier), ("student", identifier.upper())):
        row = db.query_one(_LOGIN_BY_IDENTIFIER[role], (identifier_value,))
        if row:
            return role, row
    return None


def get_account(role: str, account_id: int) -> dict | None:
    """The login fields of one account, or None if it is gone or inactive."""
    return db.query_one(_LOGIN_BY_ID[role], (account_id,))


def set_password(role: str, account_id: int, new_password: str) -> None:
    """Set a password the person chose themselves, which ends any forced change."""
    table, id_column = ROLE_TABLES[role]
    extra = "" if role == "admin" else ", must_change_password = FALSE"
    db.execute(f"UPDATE {table} SET password_hash = %s{extra} WHERE {id_column} = %s", (hash_password(new_password), account_id))


def email_owner(email: str) -> tuple[str, int] | None:
    """Which account already uses `email`, as (role, id), or None. Emails identify one account across all roles."""
    for role, (table, id_column) in ROLE_TABLES.items():
        row = db.query_one(f"SELECT {id_column} AS id FROM {table} WHERE email = %s", (email,))
        if row:
            return role, row["id"]
    return None


# --- Admin ---


def create_admin(username: str, email: str, password: str) -> int:
    return db.execute(
        "INSERT INTO admin (username, email, password_hash) VALUES (%s, %s, %s)",
        (username, email, hash_password(password)),
    )


# --- Students (F2) ---


def create_student(
    enrollment_no: str, name: str, email: str | None, mobile: str | None, course: str, semester: int, section: str | None
) -> int:
    """The temporary password is the Enrolment Number (ADR 0003)."""
    return db.execute(
        "INSERT INTO student (enrollment_no, name, email, mobile, course, semester, section,"
        " password_hash, must_change_password) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)",
        (enrollment_no, name, email, mobile, course, semester, section, hash_password(enrollment_no)),
    )


def list_students() -> list[dict]:
    """Every Student with `encoding_count`, the number of stored Face Encodings (0 means not enrolled)."""
    return db.query(
        f"SELECT {STUDENT_FIELDS},"
        " (SELECT COUNT(*) FROM face_encoding e WHERE e.student_id = student.student_id) AS encoding_count"
        " FROM student ORDER BY is_active DESC, course, semester, enrollment_no"
    )


def get_student(student_id: int) -> dict | None:
    return db.query_one(f"SELECT {STUDENT_FIELDS}, must_change_password FROM student WHERE student_id = %s", (student_id,))


def update_student(
    student_id: int, enrollment_no: str, name: str, email: str | None, mobile: str | None,
    course: str, semester: int, section: str | None,
) -> None:
    """While the Student still has the temporary password, it follows a changed Enrolment Number."""
    db.execute(
        "UPDATE student SET enrollment_no = %s, name = %s, email = %s, mobile = %s, course = %s, semester = %s,"
        " section = %s, password_hash = IF(must_change_password, %s, password_hash) WHERE student_id = %s",
        (enrollment_no, name, email, mobile, course, semester, section, hash_password(enrollment_no), student_id),
    )


def reset_student_password(student_id: int) -> bool:
    """Back to the Enrolment Number, to be changed at next login (ADR 0003). False if no such Student."""
    student = get_student(student_id)
    if student is None:
        return False
    db.execute(
        "UPDATE student SET password_hash = %s, must_change_password = TRUE WHERE student_id = %s",
        (hash_password(student["enrollment_no"]), student_id),
    )
    return True


# --- Faculty (F2) ---


def create_faculty(name: str, email: str, department: str, temporary_password: str) -> int:
    return db.execute(
        "INSERT INTO faculty (name, email, department, password_hash, must_change_password)"
        " VALUES (%s, %s, %s, %s, TRUE)",
        (name, email, department, hash_password(temporary_password)),
    )


def list_faculty(active_only: bool = False) -> list[dict]:
    where = "WHERE is_active" if active_only else ""
    return db.query(f"SELECT {FACULTY_FIELDS} FROM faculty {where} ORDER BY is_active DESC, name")


def get_faculty(faculty_id: int) -> dict | None:
    return db.query_one(f"SELECT {FACULTY_FIELDS} FROM faculty WHERE faculty_id = %s", (faculty_id,))


def update_faculty(faculty_id: int, name: str, email: str, department: str, temporary_password: str) -> None:
    """An empty `temporary_password` keeps the current password; otherwise it is reset and must be changed."""
    if temporary_password:
        db.execute(
            "UPDATE faculty SET name = %s, email = %s, department = %s, password_hash = %s,"
            " must_change_password = TRUE WHERE faculty_id = %s",
            (name, email, department, hash_password(temporary_password), faculty_id),
        )
    else:
        db.execute(
            "UPDATE faculty SET name = %s, email = %s, department = %s WHERE faculty_id = %s",
            (name, email, department, faculty_id),
        )


def set_active(role: str, account_id: int, active: bool) -> None:
    table, id_column = ROLE_TABLES[role]
    db.execute(f"UPDATE {table} SET is_active = %s WHERE {id_column} = %s", (active, account_id))


# --- Face Encodings (F3) ---
# Stored as 128 little-endian float64 values (SPEC §4). No images, ever (ADR 0002).


def _to_blob(encoding: np.ndarray) -> bytes:
    blob = np.asarray(encoding, dtype="<f8").tobytes()
    if len(blob) != 128 * 8:
        raise ValueError("a Face Encoding must have 128 numbers")
    return blob


ENCODING_BYTES = 128 * 8


def _from_blob(blob: bytes) -> np.ndarray:
    if len(blob) != ENCODING_BYTES:
        raise ValueError(f"a Face Encoding must be {ENCODING_BYTES} bytes, got {len(blob)}")
    return np.frombuffer(blob, dtype="<f8").astype(np.float64)


def replace_encodings(student_id: int, encodings: list[np.ndarray]) -> None:
    """Make `encodings` the Student's only Face Encodings, in one transaction (F3.4)."""
    with db.transaction() as cursor:
        cursor.execute("DELETE FROM face_encoding WHERE student_id = %s", (student_id,))
        cursor.executemany(
            "INSERT INTO face_encoding (student_id, encoding_vector) VALUES (%s, %s)",
            [(student_id, _to_blob(encoding)) for encoding in encodings],
        )


def encodings_of_other_students(student_id: int) -> dict[str, list[np.ndarray]]:
    """Every other *active* Student's Face Encodings, keyed by "Name (Enrolment Number)" for messages.

    Deactivated Students can't attend, so their faces don't block anyone (SPEC F3.2).
    """
    rows = db.query(
        "SELECT s.name, s.enrollment_no, e.encoding_vector FROM face_encoding e"
        " JOIN student s ON s.student_id = e.student_id WHERE e.student_id <> %s AND s.is_active",
        (student_id,),
    )
    gallery: dict[str, list[np.ndarray]] = {}
    for row in rows:
        gallery.setdefault(f"{row['name']} ({row['enrollment_no']})", []).append(_from_blob(row["encoding_vector"]))
    return gallery
