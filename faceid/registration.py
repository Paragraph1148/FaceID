"""Validation of the Admin's registration forms (SPEC F2.2).

Each `clean_*` function takes the submitted form and returns (values, errors):
`values` holds the cleaned fields and `errors` maps a field name to a message for that field.
Uniqueness is checked by the database (see `faceid.store.db.duplicate_field`).
"""

import re

from faceid.passwords import problem_with

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _text(form, field):
    return (form.get(field) or "").strip()


def _required(values, errors, field, label, max_length):
    if not values[field]:
        errors[field] = f"{label} is required."
    elif len(values[field]) > max_length:
        errors[field] = f"{label} must be at most {max_length} characters."


def _semester(values, errors):
    raw = values["semester"]
    if raw.isdigit() and 1 <= int(raw) <= 12:
        values["semester"] = int(raw)
    else:
        errors["semester"] = "Semester must be a number from 1 to 12."


def _email(values, errors, required):
    if not values["email"]:
        values["email"] = None
        if required:
            errors["email"] = "Email is required."
    elif not EMAIL.match(values["email"]) or len(values["email"]) > 100:
        errors["email"] = "Enter a valid email address."


def clean_student(form):
    fields = ("enrollment_no", "name", "email", "mobile", "course", "semester", "section")
    values = {field: _text(form, field) for field in fields}
    values["enrollment_no"] = values["enrollment_no"].upper()
    values["course"] = values["course"].upper()
    errors = {}
    _required(values, errors, "enrollment_no", "Enrolment Number", 20)
    _required(values, errors, "name", "Name", 100)
    _required(values, errors, "course", "Programme", 50)
    _semester(values, errors)
    _email(values, errors, required=False)
    if values["mobile"] and not (values["mobile"].isdigit() and len(values["mobile"]) <= 15):
        errors["mobile"] = "Mobile must be digits only, at most 15."
    values["mobile"] = values["mobile"] or None
    if len(values["section"]) > 10:
        errors["section"] = "Section must be at most 10 characters."
    values["section"] = values["section"] or None
    return values, errors


def clean_faculty(form, is_new):
    values = {field: _text(form, field) for field in ("name", "email", "department")}
    values["temporary_password"] = form.get("temporary_password") or ""
    errors = {}
    _required(values, errors, "name", "Name", 100)
    _email(values, errors, required=True)
    _required(values, errors, "department", "Department", 50)
    if is_new or values["temporary_password"]:
        problem = problem_with(values["temporary_password"])
        if problem:
            errors["temporary_password"] = problem
    return values, errors


def clean_subject(form, active_faculty_ids):
    fields = ("subject_code", "subject_name", "course", "semester", "faculty_id")
    values = {field: _text(form, field) for field in fields}
    values["subject_code"] = values["subject_code"].upper()
    values["course"] = values["course"].upper()
    errors = {}
    _required(values, errors, "subject_code", "Subject Code", 20)
    _required(values, errors, "subject_name", "Subject name", 100)
    _required(values, errors, "course", "Programme", 50)
    _semester(values, errors)
    if values["faculty_id"].isdigit() and int(values["faculty_id"]) in active_faculty_ids:
        values["faculty_id"] = int(values["faculty_id"])
    else:
        errors["faculty_id"] = "Choose an active Faculty member."
    return values, errors
