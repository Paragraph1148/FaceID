"""Password hashing with bcrypt (SPEC F1.1, N6)."""

import bcrypt

ROUNDS = 12  # bcrypt cost; tests lower it for speed
MIN_LENGTH = 8
MAX_BYTES = 72  # bcrypt only reads the first 72 bytes and bcrypt 5 rejects longer input


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=ROUNDS)).decode("ascii")


def check_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_BYTES:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("ascii"))


def problem_with(password: str) -> str | None:
    """Why `password` is unacceptable, or None if it is fine."""
    if len(password) < MIN_LENGTH:
        return f"Password must be at least {MIN_LENGTH} characters."
    if len(password.encode("utf-8")) > MAX_BYTES:
        return f"Password must be at most {MAX_BYTES} bytes."
    return None
