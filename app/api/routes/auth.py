from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models import Hospital, HospitalMembership, User
from app.models.patient_portal import PatientPortalLink
from app.schemas.patient_portal import PatientTokenRequest

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token", summary="Exchange staff credentials and hospital selection for an access token")
def issue_token(
    form: OAuth2PasswordRequestForm = Depends(),
    hospital_id: UUID = Form(...),
    db: Session = Depends(get_db),
) -> dict:
    user = db.scalar(select(User).where(User.email == form.username.lower().strip()))
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    # Fail closed: an MFA-enabled account must never receive a bearer token from
    # the password-only flow. A dedicated MFA challenge/verification endpoint
    # is a remaining Phase 1 task; until then, administrators must not enable
    # MFA on accounts that need interactive access.
    if user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-factor authentication is enabled but the verification flow is not yet available",
        )

    # RLS protects memberships, so establish the requested tenant scope before lookup.
    db.execute(
        text("SELECT set_config('app.current_hospital_id', :hospital_id, true)"),
        {"hospital_id": str(hospital_id)},
    )
    membership = db.scalar(
        select(HospitalMembership).where(
            HospitalMembership.user_id == user.id,
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="No active membership for the selected hospital")

    hospital = db.get(Hospital, hospital_id)
    if hospital is None or hospital.status != "active":
        raise HTTPException(status_code=403, detail="Hospital is not active")

    token = create_access_token(user_id=user.id, hospital_id=hospital.id)
    return {"access_token": token, "token_type": "bearer", "hospital_id": str(hospital.id)}



@router.post("/patient-token", summary="Exchange verified patient portal credentials for a hospital-scoped access token")
def issue_patient_portal_token(payload: PatientTokenRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-factor authentication is enabled but the verification flow is not yet available",
        )
    db.execute(
        text("SELECT set_config('app.current_hospital_id', :hospital_id, true)"),
        {"hospital_id": str(payload.hospital_id)},
    )
    hospital = db.get(Hospital, payload.hospital_id)
    if hospital is None or hospital.status != "active":
        raise HTTPException(status_code=403, detail="Hospital is not active")
    now = datetime.now(timezone.utc)
    active_link = db.scalar(select(PatientPortalLink.id).where(
        PatientPortalLink.hospital_id == payload.hospital_id,
        PatientPortalLink.portal_user_id == user.id,
        PatientPortalLink.status == "active",
        or_(PatientPortalLink.expires_at.is_(None), PatientPortalLink.expires_at > now),
    ).limit(1))
    if active_link is None:
        raise HTTPException(status_code=403, detail="No active verified patient portal link for this hospital")
    token = create_access_token(user_id=user.id, hospital_id=hospital.id)
    return {"access_token": token, "token_type": "bearer", "hospital_id": str(hospital.id)}
