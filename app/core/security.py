from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt
from pwdlib import PasswordHash
from app.core.config import get_settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    return password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)

def create_access_token(*, user_id: UUID, hospital_id: UUID, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "hospital_id": str(hospital_id), "iat": datetime.now(timezone.utc), "exp": expires, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
