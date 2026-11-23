from uuid import UUID
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import HospitalMembership, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

def get_current_context(token: str = Depends(oauth2_scheme), x_hospital_id: UUID = Header(..., alias="X-Hospital-ID"), db: Session = Depends(get_db)) -> tuple[User, UUID]:
    credentials_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired authentication credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access" or UUID(payload["hospital_id"]) != x_hospital_id:
            raise credentials_error
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise credentials_error from None
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise credentials_error
    membership = db.scalar(select(HospitalMembership).where(HospitalMembership.user_id == user.id, HospitalMembership.hospital_id == x_hospital_id, HospitalMembership.status == "active"))
    if membership is None:
        raise HTTPException(status_code=403, detail="No active membership for this hospital")
    return user, x_hospital_id
