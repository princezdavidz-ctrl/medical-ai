from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import Patient
from app.schemas.patient import PatientCreate, PatientRead
router = APIRouter(prefix="/patients", tags=["patients"])
@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)) -> Patient:
    _, hospital_id = context
    patient = Patient(hospital_id=hospital_id, **payload.model_dump())
    db.add(patient)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Medical record number already exists in this hospital") from None
    db.refresh(patient)
    return patient
@router.get("", response_model=list[PatientRead])
def list_patients(context: tuple = Depends(get_current_context), db: Session = Depends(get_db), limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)) -> list[Patient]:
    _, hospital_id = context
    return list(db.scalars(select(Patient).where(Patient.hospital_id == hospital_id).order_by(Patient.created_at.desc()).limit(limit).offset(offset)).all())
@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)) -> Patient:
    _, hospital_id = context
    patient = db.scalar(select(Patient).where(Patient.id == patient_id, Patient.hospital_id == hospital_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient
