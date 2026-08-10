import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from re import search

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390_000
PASSWORD_MIN_LENGTH = 8


@dataclass(frozen=True)
class SessionToken:
    raw: str
    token_hash: str


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return "$".join(
        [
            PASSWORD_ALGORITHM,
            str(PASSWORD_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(derived).decode("ascii"),
        ]
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, expected_text = password_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(expected_text.encode("ascii"))
    except (ValueError, TypeError):
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(derived, expected)


def password_policy_errors(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append("Use at least 8 characters.")
    if search(r"[A-Z]", password) is None:
        errors.append("Add one uppercase letter.")
    if search(r"\d", password) is None:
        errors.append("Add one number.")
    if search(r"[^A-Za-z0-9]", password) is None:
        errors.append("Add one special character.")
    return errors


def password_meets_policy(password: str) -> bool:
    return not password_policy_errors(password)


def hash_session_token(raw_token: str, secret_key: str) -> str:
    digest = hmac.new(
        secret_key.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def create_session_token(secret_key: str) -> SessionToken:
    raw = secrets.token_urlsafe(32)
    return SessionToken(raw=raw, token_hash=hash_session_token(raw, secret_key))
