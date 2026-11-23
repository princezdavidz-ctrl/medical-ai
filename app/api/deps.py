from uuid import UUID
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import HospitalMembership, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

def get_current_context(
    token: str = Depends(oauth2_scheme),
    x_hospital_id: UUID = Header(..., alias="X-Hospital-ID"),
    db: Session = Depends(get_db),
) -> tuple[User, UUID]:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        token_hospital_id = UUID(payload["hospital_id"])
        if payload.get("type") != "access" or token_hospital_id != x_hospital_id:
            raise credentials_error
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise credentials_error from None

    # Set the tenant context before reading any RLS-protected tenant table.
    # true means transaction-local; it is cleared automatically on commit/rollback.
    db.execute(
        text("SELECT set_config('app.current_hospital_id', :hospital_id, true)"),
        {"hospital_id": str(token_hospital_id)},
    )
    db.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )

    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise credentials_error

    membership = db.scalar(
        select(HospitalMembership).where(
            HospitalMembership.user_id == user.id,
            HospitalMembership.hospital_id == token_hospital_id,
            HospitalMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="No active membership for this hospital")
    return user, token_hospital_id
