from uuid import uuid4
import jwt
import pytest
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password

def test_password_hash_is_verified_without_storing_plaintext() -> None:
    password = "A-long-test-password-2026!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)

def test_password_policy_rejects_short_passwords() -> None:
    with pytest.raises(ValueError):
        hash_password("short")

def test_access_token_is_scoped_to_hospital() -> None:
    user_id = uuid4()
    hospital_id = uuid4()
    token = create_access_token(user_id=user_id, hospital_id=hospital_id)
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["hospital_id"] == str(hospital_id)
    assert payload["type"] == "access"

def test_access_token_rejects_tampering() -> None:
    user_id = uuid4()
    hospital_id = uuid4()
    token = create_access_token(user_id=user_id, hospital_id=hospital_id)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token + "tampered")
