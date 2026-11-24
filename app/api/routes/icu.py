from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    BedAssignment,
    Encounter,
    HospitalBed,
    HospitalMembership,
    ICUCareEvent,
    ICUObservation,
    ICUProgressNote,
    ICUStay,
    InpatientAdmission,
    PatientCareAssignment,
    Role,
    Ward,
)
from app.schemas.icu import (
    ICUCareEventCreate,
    ICUCareEventRead,
    ICUObservationCreate,
    ICUObservationRead,
    ICUProgressNoteCreate,
    ICUProgressNoteRead,
    ICUStayCreate,
    ICUStayDetailRead,
    ICUStayRead,
    ICUStepdownRequest,
)

router = APIRouter(prefix="/icu", tags=["intensive care unit"])

_ICU_NURSE_ROLES = {
    "nurse", "registered_nurse", "nursing_officer",
    "icu_nurse", "critical_care_nurse", "nursing_supervisor",
}
_ICU_CLINICIAN_ROLES = {
    "doctor", "physician", "medical_officer",
    "intensivist", "critical_care_physician",
}
_ADMIN_ROLES = {"hospital_admin", "hospital_director", "system_admin"}


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


def _require_role(
    db: Session,
    *,
    user_id: UUID,
    hospital_id: UUID,
    allowed: set[str],
    department_id: UUID | None = None,
    allow_admin: bool = True,
) -> tuple[HospitalMembership, str]:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or (
        role_name not in allowed and not (allow_admin and role_name in _ADMIN_ROLES)
    ):
        raise HTTPException(status_code=403, detail={"code": "icu_role_not_authorized"})
    if role_name not in _ADMIN_ROLES and department_id is not None:
        if membership.department_id != department_id:
            raise HTTPException(status_code=403, detail={"code": "icu_department_scope_required"})
    return membership, role_name


def _restore_tenant_context(db: Session, *, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(
        text("SELECT set_config('app.current_hospital_id', :hospital_id, true)"),
        {"hospital_id": str(hospital_id)},
    )
    db.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


def _get_stay(
    db: Session, *, hospital_id: UUID, stay_id: UUID, lock: bool = False
) -> ICUStay:
    query = select(ICUStay).where(
        ICUStay.id == stay_id, ICUStay.hospital_id == hospital_id
    )
    if lock:
        query = query.with_for_update()
    stay = db.scalar(query)
    if stay is None:
        raise HTTPException(status_code=404, detail={"code": "icu_stay_not_found"})
    return stay


def _has_assignment(
    db: Session, *, user_id: UUID, hospital_id: UUID, stay: ICUStay
) -> bool:
    now = datetime.now(timezone.utc)
    return db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == stay.patient_id,
        PatientCareAssignment.encounter_id == stay.encounter_id,
        PatientCareAssignment.staff_user_id == user_id,
        PatientCareAssignment.department_id == stay.department_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ).limit(1)) is not None


def _require_active_inpatient_admission(
    db: Session, *, hospital_id: UUID, stay: ICUStay
) -> InpatientAdmission:
    admission = db.scalar(select(InpatientAdmission).where(
        InpatientAdmission.id == stay.admission_id,
        InpatientAdmission.hospital_id == hospital_id,
    ).with_for_update())
    if admission is None or admission.status != "admitted":
        raise HTTPException(status_code=409, detail={"code": "inpatient_admission_not_active"})
    return admission


def _require_stay_access(
    db: Session, *, user_id: UUID, hospital_id: UUID, stay: ICUStay,
    allowed: set[str] | None = None,
    allow_admin: bool = False,
) -> str:
    allowed = allowed or (_ICU_NURSE_ROLES | _ICU_CLINICIAN_ROLES)
    _, role_name = _require_role(
        db, user_id=user_id, hospital_id=hospital_id,
        allowed=allowed, department_id=stay.department_id,
        allow_admin=allow_admin,
    )
    if role_name not in _ADMIN_ROLES and not _has_assignment(
        db, user_id=user_id, hospital_id=hospital_id, stay=stay
    ):
        raise HTTPException(status_code=404, detail={"code": "icu_stay_not_found"})
    return role_name


def _audit(
    db: Session, *, hospital_id: UUID, user_id: UUID,
    action: str, resource_type: str, resource_id: UUID | None,
) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id,
        action=action, resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
    )


def _stay_detail(db: Session, stay: ICUStay) -> dict:
    observations = db.scalars(select(ICUObservation).where(
        ICUObservation.hospital_id == stay.hospital_id,
        ICUObservation.stay_id == stay.id,
    ).order_by(ICUObservation.observed_at.desc()).limit(1000)).all()
    events = db.scalars(select(ICUCareEvent).where(
        ICUCareEvent.hospital_id == stay.hospital_id,
        ICUCareEvent.stay_id == stay.id,
    ).order_by(ICUCareEvent.performed_at.desc()).limit(500)).all()
    notes = db.scalars(select(ICUProgressNote).where(
        ICUProgressNote.hospital_id == stay.hospital_id,
        ICUProgressNote.stay_id == stay.id,
    ).order_by(ICUProgressNote.signed_at.desc()).limit(200)).all()
    return {
        "stay": stay,
        "observations": observations,
        "care_events": events,
        "progress_notes": notes,
    }


@router.post("/stays", response_model=ICUStayRead, status_code=status.HTTP_201_CREATED)
def start_icu_stay(
    payload: ICUStayCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ICUStay:
    user, hospital_id = context
    admission = db.scalar(select(InpatientAdmission).where(
        InpatientAdmission.id == payload.admission_id,
        InpatientAdmission.hospital_id == hospital_id,
    ).with_for_update())
    if admission is None:
        raise HTTPException(status_code=404, detail={"code": "inpatient_admission_not_found"})
    if admission.status != "admitted":
        raise HTTPException(status_code=409, detail={"code": "patient_must_be_admitted_before_icu_stay"})
    bed_assignment = db.scalar(select(BedAssignment).where(
        BedAssignment.hospital_id == hospital_id,
        BedAssignment.admission_id == admission.id,
        BedAssignment.status == "active",
    ).with_for_update())
    if bed_assignment is None:
        raise HTTPException(status_code=409, detail={"code": "active_inpatient_bed_assignment_required"})
    bed = db.scalar(select(HospitalBed).where(
        HospitalBed.id == bed_assignment.bed_id,
        HospitalBed.hospital_id == hospital_id,
    ))
    if bed is None or bed.status != "occupied" or bed.ward_id != admission.ward_id:
        raise HTTPException(status_code=409, detail={"code": "occupied_admission_bed_required"})
    ward = db.scalar(select(Ward).where(
        Ward.id == bed.ward_id, Ward.hospital_id == hospital_id
    ))
    if ward is None or ward.status != "active" or ward.ward_type != "icu":
        raise HTTPException(status_code=422, detail={"code": "admission_bed_is_not_in_active_icu_ward"})
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == admission.encounter_id,
        Encounter.hospital_id == hospital_id,
    ))
    if encounter is None or encounter.status != "in_progress" or encounter.department_id != ward.department_id:
        raise HTTPException(status_code=409, detail={"code": "active_icu_inpatient_encounter_required"})
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_ICU_CLINICIAN_ROLES, department_id=ward.department_id,
        allow_admin=False,
    )
    now = datetime.now(timezone.utc)
    if not db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == admission.patient_id,
        PatientCareAssignment.encounter_id == admission.encounter_id,
        PatientCareAssignment.staff_user_id == user.id,
        PatientCareAssignment.department_id == ward.department_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ).limit(1)):
        raise HTTPException(status_code=403, detail={"code": "assigned_icu_clinician_required"})
    stay = ICUStay(
        hospital_id=hospital_id,
        admission_id=admission.id,
        patient_id=admission.patient_id,
        encounter_id=admission.encounter_id,
        bed_assignment_id=bed_assignment.id,
        ward_id=ward.id,
        department_id=ward.department_id,
        started_by_user_id=user.id,
        status="active",
        admission_reason=payload.admission_reason,
        started_at=now,
    )
    db.add(stay)
    try:
        db.flush()
        _audit(
            db, hospital_id=hospital_id, user_id=user.id,
            action="icu.stay.started", resource_type="icu_stay", resource_id=stay.id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "admission_already_has_active_icu_stay"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(stay)
    return stay


@router.get("/stays", response_model=list[ICUStayRead])
def list_icu_stays(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    stay_status: str | None = Query(default=None, alias="status", max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ICUStay]:
    user, hospital_id = context
    membership, role_name = _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_ICU_NURSE_ROLES | _ICU_CLINICIAN_ROLES,
    )
    query = select(ICUStay).where(ICUStay.hospital_id == hospital_id)
    if role_name not in _ADMIN_ROLES:
        now = datetime.now(timezone.utc)
        assigned_encounters = select(PatientCareAssignment.encounter_id).where(
            PatientCareAssignment.hospital_id == hospital_id,
            PatientCareAssignment.staff_user_id == user.id,
            PatientCareAssignment.department_id == membership.department_id,
            PatientCareAssignment.status == "active",
            PatientCareAssignment.valid_from <= now,
            or_(
                PatientCareAssignment.valid_until.is_(None),
                PatientCareAssignment.valid_until > now,
            ),
        )
        query = query.where(
            ICUStay.department_id == membership.department_id,
            ICUStay.encounter_id.in_(assigned_encounters),
        )
    if stay_status is not None:
        query = query.where(ICUStay.status == stay_status)
    stays = list(db.scalars(
        query.order_by(ICUStay.started_at.desc()).limit(limit).offset(offset)
    ).all())
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="icu.stays.viewed", resource_type="icu_stay_list", resource_id=None,
    )
    db.commit()
    return stays


@router.get("/stays/{stay_id}", response_model=ICUStayDetailRead)
def get_icu_stay(
    stay_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    stay = _get_stay(db, hospital_id=hospital_id, stay_id=stay_id)
    _require_stay_access(
        db, user_id=user.id, hospital_id=hospital_id, stay=stay, allow_admin=True,
    )
    result = _stay_detail(db, stay)
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="icu.stay.viewed", resource_type="icu_stay", resource_id=stay.id,
    )
    db.commit()
    return result


@router.post(
    "/stays/{stay_id}/observations",
    response_model=ICUObservationRead,
    status_code=status.HTTP_201_CREATED,
)
def record_icu_observation(
    stay_id: UUID,
    payload: ICUObservationCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ICUObservation:
    user, hospital_id = context
    stay = _get_stay(db, hospital_id=hospital_id, stay_id=stay_id, lock=True)
    _require_stay_access(db, user_id=user.id, hospital_id=hospital_id, stay=stay)
    _require_active_inpatient_admission(db, hospital_id=hospital_id, stay=stay)
    if stay.status == "closed":
        raise HTTPException(status_code=409, detail={"code": "icu_stay_closed"})
    if payload.observed_at < stay.started_at:
        raise HTTPException(status_code=422, detail={"code": "icu_observation_before_stay_start"})
    observation = ICUObservation(
        hospital_id=hospital_id, stay_id=stay.id,
        recorded_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(observation)
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="icu.observation.recorded",
        resource_type="icu_observation", resource_id=observation.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(observation)
    return observation


@router.post(
    "/stays/{stay_id}/events",
    response_model=ICUCareEventRead,
    status_code=status.HTTP_201_CREATED,
)
def record_icu_care_event(
    stay_id: UUID,
    payload: ICUCareEventCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ICUCareEvent:
    user, hospital_id = context
    stay = _get_stay(db, hospital_id=hospital_id, stay_id=stay_id, lock=True)
    _require_stay_access(db, user_id=user.id, hospital_id=hospital_id, stay=stay)
    _require_active_inpatient_admission(db, hospital_id=hospital_id, stay=stay)
    if stay.status == "closed":
        raise HTTPException(status_code=409, detail={"code": "icu_stay_closed"})
    if payload.performed_at < stay.started_at:
        raise HTTPException(status_code=422, detail={"code": "icu_event_before_stay_start"})
    event = ICUCareEvent(
        hospital_id=hospital_id, stay_id=stay.id,
        performed_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(event)
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="icu.care_event.recorded",
        resource_type="icu_care_event", resource_id=event.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(event)
    return event


@router.post(
    "/stays/{stay_id}/notes",
    response_model=ICUProgressNoteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_icu_progress_note(
    stay_id: UUID,
    payload: ICUProgressNoteCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ICUProgressNote:
    user, hospital_id = context
    stay = _get_stay(db, hospital_id=hospital_id, stay_id=stay_id, lock=True)
    _require_stay_access(db, user_id=user.id, hospital_id=hospital_id, stay=stay)
    _require_active_inpatient_admission(db, hospital_id=hospital_id, stay=stay)
    if stay.status == "closed":
        raise HTTPException(status_code=409, detail={"code": "icu_stay_closed"})
    note = ICUProgressNote(
        hospital_id=hospital_id, stay_id=stay.id,
        author_user_id=user.id, **payload.model_dump(),
    )
    db.add(note)
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="icu.progress_note.signed",
        resource_type="icu_progress_note", resource_id=note.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(note)
    return note


@router.post("/stays/{stay_id}/stepdown-request", response_model=ICUStayRead)
def request_icu_stepdown(
    stay_id: UUID,
    payload: ICUStepdownRequest,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ICUStay:
    user, hospital_id = context
    stay = _get_stay(db, hospital_id=hospital_id, stay_id=stay_id, lock=True)
    _require_stay_access(
        db, user_id=user.id, hospital_id=hospital_id, stay=stay,
        allowed=_ICU_CLINICIAN_ROLES,
    )
    _require_active_inpatient_admission(db, hospital_id=hospital_id, stay=stay)
    if stay.status != "active":
        raise HTTPException(status_code=409, detail={"code": "icu_stay_not_active"})
    stay.status = "stepdown_requested"
    stay.stepdown_requested_by_user_id = user.id
    stay.stepdown_requested_at = datetime.now(timezone.utc)
    stay.stepdown_reason = payload.reason
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="icu.stepdown.requested", resource_type="icu_stay", resource_id=stay.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(stay)
    return stay


@router.post("/stays/{stay_id}/close", response_model=ICUStayRead)
def close_icu_stay_after_hospital_discharge(
    stay_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ICUStay:
    user, hospital_id = context
    stay = _get_stay(db, hospital_id=hospital_id, stay_id=stay_id, lock=True)
    _require_stay_access(
        db, user_id=user.id, hospital_id=hospital_id, stay=stay,
        allowed=_ICU_CLINICIAN_ROLES,
    )
    if stay.status == "closed":
        raise HTTPException(status_code=409, detail={"code": "icu_stay_already_closed"})
    admission = db.scalar(select(InpatientAdmission).where(
        InpatientAdmission.id == stay.admission_id,
        InpatientAdmission.hospital_id == hospital_id,
    ))
    if admission is None or admission.status != "discharged":
        raise HTTPException(status_code=409, detail={"code": "inpatient_discharge_must_be_completed_before_icu_close"})
    stay.status = "closed"
    stay.closed_by_user_id = user.id
    stay.closed_at = datetime.now(timezone.utc)
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="icu.stay.closed", resource_type="icu_stay", resource_id=stay.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(stay)
    return stay
