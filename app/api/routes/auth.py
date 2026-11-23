from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models import Hospital, HospitalMembership, User
router = APIRouter(prefix="/auth", tags=["authentication"])
@router.post("/token", summary="Exchange staff credentials for a hospital-scoped access token")
def issue_token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == form.username.lower().strip()))
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    memberships = db.scalars(select(HospitalMembership).where(HospitalMembership.user_id == user.id, HospitalMembership.status == "active")).all()
    if len(memberships) != 1:
        raise HTTPException(status_code=400, detail="A single active hospital membership is required for token issuance")
    membership = memberships[0]
    hospital = db.get(Hospital, membership.hospital_id)
    if hospital is None or hospital.status != "active":
        raise HTTPException(status_code=403, detail="Hospital is not active")
    token = create_access_token(user_id=user.id, hospital_id=hospital.id)
    return {"access_token": token, "token_type": "bearer", "hospital_id": str(hospital.id)}
