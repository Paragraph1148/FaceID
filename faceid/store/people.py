"""Admin, Faculty and Student rows (SPEC F1, F2)."""

from faceid.passwords import hash_password
from faceid.store import db

ROLE_TABLES = {
    "admin": ("admin", "admin_id"),
    "faculty": ("faculty", "faculty_id"),
    "student": ("student", "student_id"),
}


def create_admin(username, email, password):
    return db.execute(
        "INSERT INTO admin (username, email, password_hash) VALUES (%s, %s, %s)",
        (username, email, hash_password(password)),
    )


def create_faculty(name, email, department, temporary_password):
    return db.execute(
        "INSERT INTO faculty (name, email, department, password_hash, must_change_password)"
        " VALUES (%s, %s, %s, %s, TRUE)",
        (name, email, department, hash_password(temporary_password)),
    )


def create_student(enrollment_no, name, email, mobile, course, semester, section):
    """The temporary password is the Enrolment Number (ADR 0003)."""
    return db.execute(
        "INSERT INTO student (enrollment_no, name, email, mobile, course, semester, section,"
        " password_hash, must_change_password) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)",
        (enrollment_no, name, email, mobile, course, semester, section, hash_password(enrollment_no)),
    )


def find_login(identifier):
    """The account a login identifier refers to, as (role, row), or None.

    Admin and Faculty log in with their email address, Students with their Enrolment Number.
    Inactive Faculty and Students cannot log in.
    """
    row = db.query_one("SELECT admin_id AS id, username AS name, password_hash FROM admin WHERE email = %s", (identifier,))
    if row:
        return "admin", {**row, "must_change_password": False}
    row = db.query_one(
        "SELECT faculty_id AS id, name, password_hash, must_change_password FROM faculty"
        " WHERE email = %s AND is_active",
        (identifier,),
    )
    if row:
        return "faculty", row
    row = db.query_one(
        "SELECT student_id AS id, name, password_hash, must_change_password FROM student"
        " WHERE enrollment_no = %s AND is_active",
        (identifier,),
    )
    if row:
        return "student", row
    return None


def get_account(role, account_id):
    """The login-relevant fields of one account, or None if it is gone or inactive."""
    if role == "admin":
        row = db.query_one("SELECT admin_id AS id, username AS name, password_hash FROM admin WHERE admin_id = %s", (account_id,))
        return {**row, "must_change_password": False} if row else None
    table, id_column = ROLE_TABLES[role]
    return db.query_one(
        f"SELECT {id_column} AS id, name, password_hash, must_change_password FROM {table}"
        f" WHERE {id_column} = %s AND is_active",
        (account_id,),
    )


def set_password(role, account_id, new_password):
    table, id_column = ROLE_TABLES[role]
    if role == "admin":
        db.execute(f"UPDATE admin SET password_hash = %s WHERE admin_id = %s", (hash_password(new_password), account_id))
    else:
        db.execute(
            f"UPDATE {table} SET password_hash = %s, must_change_password = FALSE WHERE {id_column} = %s",
            (hash_password(new_password), account_id),
        )
