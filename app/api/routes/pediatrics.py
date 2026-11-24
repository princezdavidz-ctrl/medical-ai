from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    Department,
    Encounter,
    HospitalMembership,
    Patient,
    PatientCareAssignment,
    PediatricCareRecord,
    PediatricClinicalNote,
    PediatricDevelopmentalScreening,
    PediatricGrowthObservation,
    PediatricImmunizationHistory,
    Role,
)
from app.schemas.pediatrics import (
    PediatricCareRecordCreate,
    PediatricCareRecordDetailRead,
    PediatricCareRecordRead,
    PediatricClinicalNoteCreate,
    PediatricDevelopmentalScreeningCreate,
    PediatricDevelopmentalScreeningRead,
    PediatricGrowthObservationCreate,
    PediatricGrowthObservationRead,
    PediatricImmunizationHistoryCreate,
    PediatricImmunizationHistoryRead,
)

router = APIRouter(prefix="/pediatrics", tags=["pediatrics and child health"])

_PEDIATRIC_ROLES = {
    "pediatrician", "pediatric_nurse", "child_health_nurse",
    "child_health_officer", "doctor", "medical_officer",
    "nurse", "registered_nurse",
}


def _membership(db: Session, *, user_id: UUID, hospital_id: UUID):
    return db.scalar(
        select(HospitalMembership)
        .join(Role, Role.id == HospitalMembership.role_id)
        .where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == user_id,
            HospitalMembership.status == "active",
        )
    )


def _role_name(db: Session, membership: HospitalMembership | None) -> str:
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _restore_tenant_context(db: Session, *, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(
        text("SELECT set_config('app.current_hospital_id', :hospital_id, true)"),
        {"hospital_id": str(hospital_id)},
    )
    db.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


def _require_membership(
    db: Session, *, user_id: UUID, hospital_id: UUID, department_id: UUID
) -> HospitalMembership:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    if membership is None or _role_name(db, membership) not in _PEDIATRIC_ROLES:
        raise HTTPException(status_code=403, detail={"code": "pediatric_role_required"})
    if membership.department_id != department_id:
        raise HTTPException(status_code=403, detail={"code": "pediatric_department_scope_required"})
    return membership


def _has_assignment(
    db: Session, *, user_id: UUID, hospital_id: UUID, record: PediatricCareRecord
) -> bool:
    now = datetime.now(timezone.utc)
    return db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == record.patient_id,
        PatientCareAssignment.encounter_id == record.encounter_id,
        PatientCareAssignment.department_id == record.department_id,
        PatientCareAssignment.staff_user_id == user_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        (
            PatientCareAssignment.valid_until.is_(None)
            | (PatientCareAssignment.valid_until > now)
        ),
    ).limit(1)) is not None


def _get_record(
    db: Session, *, hospital_id: UUID, record_id: UUID, lock: bool = False
) -> PediatricCareRecord:
    query = select(PediatricCareRecord).where(
        PediatricCareRecord.id == record_id,
        PediatricCareRecord.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    record = db.scalar(query)
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "pediatric_record_not_found"})
    return record


def _require_record_access(
    db: Session, *, user_id: UUID, hospital_id: UUID, record: PediatricCareRecord,
    require_active: bool = True,
) -> None:
    _require_membership(
        db, user_id=user_id, hospital_id=hospital_id,
        department_id=record.department_id,
    )
    if require_active and record.status != "active":
        raise HTTPException(status_code=409, detail={"code": "pediatric_record_closed"})
    if not _has_assignment(db, user_id=user_id, hospital_id=hospital_id, record=record):
        raise HTTPException(status_code=404, detail={"code": "pediatric_record_not_found"})


def _record_detail(db: Session, record: PediatricCareRecord) -> dict:
    return {
        "record": record,
        "growth_observations": db.scalars(
            select(PediatricGrowthObservation).where(
                PediatricGrowthObservation.hospital_id == record.hospital_id,
                PediatricGrowthObservation.care_record_id == record.id,
            ).order_by(PediatricGrowthObservation.observed_at)
        ).all(),
        "developmental_screenings": db.scalars(
            select(PediatricDevelopmentalScreening).where(
                PediatricDevelopmentalScreening.hospital_id == record.hospital_id,
                PediatricDevelopmentalScreening.care_record_id == record.id,
            ).order_by(PediatricDevelopmentalScreening.screened_at)
        ).all(),
        "immunization_history": db.scalars(
            select(PediatricImmunizationHistory).where(
                PediatricImmunizationHistory.hospital_id == record.hospital_id,
                PediatricImmunizationHistory.care_record_id == record.id,
            ).order_by(PediatricImmunizationHistory.administered_at.nulls_last())
        ).all(),
        "notes": db.scalars(
            select(PediatricClinicalNote).where(
                PediatricClinicalNote.hospital_id == record.hospital_id,
                PediatricClinicalNote.care_record_id == record.id,
            ).order_by(PediatricClinicalNote.signed_at)
        ).all(),
    }


@router.post(
    "/encounters/{encounter_id}/records",
    response_model=PediatricCareRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def create_pediatric_record(
    encounter_id: UUID,
    payload: PediatricCareRecordCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> PediatricCareRecord:
    user, hospital_id = context
    _require_membership(
        db, user_id=user.id, hospital_id=hospital_id,
        department_id=payload.department_id,
    )
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is None or encounter.status != "in_progress":
        raise HTTPException(status_code=404, detail={"code": "active_pediatric_encounter_not_found"})
    if encounter.department_id != payload.department_id:
        raise HTTPException(status_code=403, detail={"code": "pediatric_encounter_department_mismatch"})
    patient = db.scalar(select(Patient).where(
        Patient.id == encounter.patient_id,
        Patient.hospital_id == hospital_id,
        Patient.status == "active",
    ).with_for_update())
    if patient is None or patient.date_of_birth is None:
        raise HTTPException(status_code=409, detail={"code": "pediatric_patient_date_of_birth_required"})
    today = date.today()
    age_years = today.year - patient.date_of_birth.year - (
        (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
    )
    if age_years >= 18 or patient.date_of_birth > today:
        raise HTTPException(status_code=422, detail={"code": "patient_not_eligible_for_pediatric_module"})
    department = db.scalar(select(Department).where(
        Department.id == payload.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "active_pediatric_department_not_found"})
    now = datetime.now(timezone.utc)
    assignment = db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == patient.id,
        PatientCareAssignment.encounter_id == encounter.id,
        PatientCareAssignment.department_id == department.id,
        PatientCareAssignment.staff_user_id == user.id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        (
            PatientCareAssignment.valid_until.is_(None)
            | (PatientCareAssignment.valid_until > now)
        ),
    ).limit(1))
    if assignment is None:
        raise HTTPException(status_code=403, detail={"code": "assigned_pediatric_patient_required"})
    record = PediatricCareRecord(
        hospital_id=hospital_id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        department_id=department.id,
        created_by_user_id=user.id,
        status="active",
    )
    db.add(record)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="pediatrics.record.created", resource_type="pediatric_care_record",
            resource_id=str(record.id),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "pediatric_record_already_exists"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(record)
    return record


@router.get("/records/{record_id}", response_model=PediatricCareRecordDetailRead)
def get_pediatric_record(
    record_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    record = _get_record(db, hospital_id=hospital_id, record_id=record_id)
    _require_record_access(
        db, user_id=user.id, hospital_id=hospital_id, record=record,
        require_active=False,
    )
    result = _record_detail(db, record)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="pediatrics.record.viewed", resource_type="pediatric_care_record",
        resource_id=str(record.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return result


@router.post(
    "/records/{record_id}/growth-observations",
    response_model=PediatricGrowthObservationRead,
    status_code=status.HTTP_201_CREATED,
)
def add_pediatric_growth_observation(
    record_id: UUID,
    payload: PediatricGrowthObservationCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> PediatricGrowthObservation:
    user, hospital_id = context
    record = _get_record(db, hospital_id=hospital_id, record_id=record_id, lock=True)
    _require_record_access(db, user_id=user.id, hospital_id=hospital_id, record=record)
    observation = PediatricGrowthObservation(
        hospital_id=hospital_id, care_record_id=record.id,
        recorded_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(observation)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="pediatrics.growth_observation.recorded", resource_type="pediatric_care_record",
        resource_id=str(record.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(observation)
    return observation


@router.post(
    "/records/{record_id}/developmental-screenings",
    response_model=PediatricDevelopmentalScreeningRead,
    status_code=status.HTTP_201_CREATED,
)
def add_developmental_screening(
    record_id: UUID,
    payload: PediatricDevelopmentalScreeningCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> PediatricDevelopmentalScreening:
    user, hospital_id = context
    record = _get_record(db, hospital_id=hospital_id, record_id=record_id, lock=True)
    _require_record_access(db, user_id=user.id, hospital_id=hospital_id, record=record)
    screening = PediatricDevelopmentalScreening(
        hospital_id=hospital_id, care_record_id=record.id,
        recorded_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(screening)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="pediatrics.developmental_screening.recorded", resource_type="pediatric_care_record",
        resource_id=str(record.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(screening)
    return screening


@router.post(
    "/records/{record_id}/immunization-history",
    response_model=PediatricImmunizationHistoryRead,
    status_code=status.HTTP_201_CREATED,
)
def add_immunization_history(
    record_id: UUID,
    payload: PediatricImmunizationHistoryCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> PediatricImmunizationHistory:
    user, hospital_id = context
    record = _get_record(db, hospital_id=hospital_id, record_id=record_id, lock=True)
    _require_record_access(db, user_id=user.id, hospital_id=hospital_id, record=record)
    history = PediatricImmunizationHistory(
        hospital_id=hospital_id, care_record_id=record.id,
        recorded_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(history)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="pediatrics.immunization_history.recorded", resource_type="pediatric_care_record",
        resource_id=str(record.id),
        metadata={"record_status": payload.record_status, "source": payload.source},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(history)
    return history


@router.post(
    "/records/{record_id}/notes",
    response_model=PediatricClinicalNoteRead,
    status_code=status.HTTP_201_CREATED,
)
def add_pediatric_note(
    record_id: UUID,
    payload: PediatricClinicalNoteCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> PediatricClinicalNote:
    user, hospital_id = context
    record = _get_record(db, hospital_id=hospital_id, record_id=record_id, lock=True)
    _require_record_access(db, user_id=user.id, hospital_id=hospital_id, record=record)
    note = PediatricClinicalNote(
        hospital_id=hospital_id, care_record_id=record.id,
        authored_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(note)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="pediatrics.note.signed", resource_type="pediatric_care_record",
        resource_id=str(record.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(note)
    return note
