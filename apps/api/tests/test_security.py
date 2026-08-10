from app.core.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    password_hash = hash_password("correct-password")

    assert password_hash != "correct-password"
    assert verify_password("correct-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_session_token_hash_is_stable_and_secret_bound() -> None:
    session_token = create_session_token("secret-a")

    assert hash_session_token(session_token.raw, "secret-a") == session_token.token_hash
    assert hash_session_token(session_token.raw, "secret-b") != session_token.token_hash
