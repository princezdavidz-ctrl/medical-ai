from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    Department,
    EmergencyCareEvent,
    EmergencyNote,
    EmergencyTriageAssessment,
    EmergencyVisit,
    Encounter,
    HospitalMembership,
    Patient,
    PatientCareAssignment,
    Role,
)
from app.schemas.emergency import (
    EmergencyCareEventCreate,
    EmergencyCareEventRead,
    EmergencyDispositionCreate,
    EmergencyNoteCreate,
    EmergencyNoteRead,
    EmergencyQueueItemRead,
    EmergencyTriageCreate,
    EmergencyTriageRead,
    EmergencyVisitCreate,
    EmergencyVisitDetailRead,
    EmergencyVisitRead,
)

router = APIRouter(prefix="/emergency", tags=["emergency and trauma"])

_REGISTRATION_ROLES = {
    "registration_clerk", "receptionist", "emergency_registrar",
    "medical_records_officer",
}
_EMERGENCY_NURSE_ROLES = {
    "nurse", "registered_nurse", "nursing_officer", "triage_nurse", "emergency_nurse",
}
_CLINICIAN_ROLES = {
    "doctor", "physician", "medical_officer", "emergency_physician",
    "emergency_doctor", "surgeon", "pediatrician",
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
        raise HTTPException(status_code=403, detail={"code": "emergency_role_not_authorized"})
    if role_name not in _ADMIN_ROLES and department_id is not None:
        if membership.department_id != department_id:
            raise HTTPException(status_code=403, detail={"code": "emergency_department_scope_required"})
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


def _get_visit(
    db: Session, *, hospital_id: UUID, visit_id: UUID, lock: bool = False
) -> EmergencyVisit:
    query = select(EmergencyVisit).where(
        EmergencyVisit.id == visit_id,
        EmergencyVisit.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    visit = db.scalar(query)
    if visit is None:
        raise HTTPException(status_code=404, detail={"code": "emergency_visit_not_found"})
    return visit


def _has_assignment(
    db: Session, *, user_id: UUID, hospital_id: UUID, visit: EmergencyVisit
) -> bool:
    now = datetime.now(timezone.utc)
    return db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == visit.patient_id,
        PatientCareAssignment.encounter_id == visit.encounter_id,
        PatientCareAssignment.staff_user_id == user_id,
        PatientCareAssignment.department_id == visit.department_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ).limit(1)) is not None


def _ensure_assignment(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    visit: EmergencyVisit, reason: str, now: datetime,
) -> None:
    if _has_assignment(db, user_id=user_id, hospital_id=hospital_id, visit=visit):
        return
    db.add(PatientCareAssignment(
        hospital_id=hospital_id,
        patient_id=visit.patient_id,
        staff_user_id=user_id,
        assigned_by_user_id=user_id,
        department_id=visit.department_id,
        encounter_id=visit.encounter_id,
        assignment_reason=reason,
        status="active",
        valid_from=now,
    ))


def _require_visit_read(
    db: Session, *, user_id: UUID, hospital_id: UUID, visit: EmergencyVisit
) -> str:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if role_name in _REGISTRATION_ROLES | _ADMIN_ROLES:
        return role_name
    if role_name in _EMERGENCY_NURSE_ROLES and (
        membership.department_id == visit.department_id
        and visit.status in {"arrived", "waiting", "in_treatment"}
    ):
        return role_name
    if role_name not in _CLINICIAN_ROLES or not _has_assignment(
        db, user_id=user_id, hospital_id=hospital_id, visit=visit
    ):
        raise HTTPException(status_code=404, detail={"code": "emergency_visit_not_found"})
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


def _visit_detail(db: Session, visit: EmergencyVisit) -> dict:
    patient = db.scalar(select(Patient).where(
        Patient.id == visit.patient_id, Patient.hospital_id == visit.hospital_id
    ))
    triage = db.scalars(select(EmergencyTriageAssessment).where(
        EmergencyTriageAssessment.hospital_id == visit.hospital_id,
        EmergencyTriageAssessment.visit_id == visit.id,
    ).order_by(EmergencyTriageAssessment.revision)).all()
    events = db.scalars(select(EmergencyCareEvent).where(
        EmergencyCareEvent.hospital_id == visit.hospital_id,
        EmergencyCareEvent.visit_id == visit.id,
    ).order_by(EmergencyCareEvent.performed_at)).all()
    notes = db.scalars(select(EmergencyNote).where(
        EmergencyNote.hospital_id == visit.hospital_id,
        EmergencyNote.visit_id == visit.id,
    ).order_by(EmergencyNote.signed_at)).all()
    return {
        "visit": visit,
        "patient": {
            "id": patient.id,
            "medical_record_number": patient.medical_record_number,
            "given_name": patient.given_name,
            "preferred_name": patient.preferred_name,
            "family_name": patient.family_name,
            "date_of_birth": patient.date_of_birth,
            "administrative_sex": patient.administrative_sex,
        } if patient is not None else None,
        "triage_history": triage,
        "care_events": events,
        "notes": notes,
    }


@router.post("/visits", response_model=EmergencyVisitRead, status_code=status.HTTP_201_CREATED)
def create_emergency_visit(
    payload: EmergencyVisitCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> EmergencyVisit:
    user, hospital_id = context
    membership, role_name = _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_REGISTRATION_ROLES | _EMERGENCY_NURSE_ROLES | _CLINICIAN_ROLES,
    )
    patient = db.scalar(select(Patient).where(
        Patient.id == payload.patient_id, Patient.hospital_id == hospital_id
    ).with_for_update())
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    if patient.status != "active":
        raise HTTPException(status_code=409, detail={"code": "patient_not_active"})
    department = db.scalar(select(Department).where(
        Department.id == payload.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "emergency_department_not_found"})
    if role_name not in _REGISTRATION_ROLES | _ADMIN_ROLES and membership.department_id != department.id:
        raise HTTPException(status_code=403, detail={"code": "emergency_department_scope_required"})

    now = datetime.now(timezone.utc)
    encounter = Encounter(
        hospital_id=hospital_id,
        patient_id=patient.id,
        department_id=department.id,
        encounter_type="emergency",
        status="in_progress",
        chief_complaint=payload.chief_complaint,
        started_at=now,
    )
    db.add(encounter)
    db.flush()
    visit = EmergencyVisit(
        hospital_id=hospital_id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        department_id=department.id,
        arrival_mode=payload.arrival_mode,
        arrival_note=payload.arrival_note,
        status="arrived",
        priority="untriaged",
        arrival_at=now,
        created_by_user_id=user.id,
    )
    db.add(visit)
    try:
        db.flush()
        _audit(
            db, hospital_id=hospital_id, user_id=user.id,
            action="emergency.visit.arrived",
            resource_type="emergency_visit", resource_id=visit.id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "patient_already_has_active_emergency_visit"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(visit)
    return visit


@router.get("/visits", response_model=list[EmergencyQueueItemRead])
def list_emergency_visits(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    visit_status: str | None = Query(default=None, alias="status", max_length=32),
    department_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    user, hospital_id = context
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if role_name not in _REGISTRATION_ROLES | _ADMIN_ROLES | _EMERGENCY_NURSE_ROLES | _CLINICIAN_ROLES:
        raise HTTPException(status_code=403, detail={"code": "emergency_read_role_required"})
    now = datetime.now(timezone.utc)
    query = select(EmergencyVisit).where(EmergencyVisit.hospital_id == hospital_id)
    if role_name not in _REGISTRATION_ROLES | _ADMIN_ROLES:
        if membership.department_id is None:
            raise HTTPException(status_code=403, detail={"code": "emergency_department_scope_required"})
        query = query.where(EmergencyVisit.department_id == membership.department_id)
        if role_name in _EMERGENCY_NURSE_ROLES:
            query = query.where(EmergencyVisit.status.in_(("arrived", "waiting", "in_treatment")))
        else:
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
            query = query.where(EmergencyVisit.encounter_id.in_(assigned_encounters))
    elif department_id is not None:
        query = query.where(EmergencyVisit.department_id == department_id)
    if visit_status is not None:
        query = query.where(EmergencyVisit.status == visit_status)
    visits = list(db.scalars(query.order_by(
        case(
            (EmergencyVisit.priority == "resuscitation", 0),
            (EmergencyVisit.priority == "emergent", 1),
            (EmergencyVisit.priority == "urgent", 2),
            (EmergencyVisit.priority == "less_urgent", 3),
            (EmergencyVisit.priority == "non_urgent", 4),
            else_=5,
        ),
        EmergencyVisit.arrival_at.asc(),
    ).limit(limit).offset(offset)).all())
    results = []
    for visit in visits:
        patient = db.scalar(select(Patient).where(
            Patient.id == visit.patient_id, Patient.hospital_id == hospital_id
        ))
        if patient is not None:
            results.append({
                "visit": visit,
                "patient": {
                    "id": patient.id,
                    "medical_record_number": patient.medical_record_number,
                    "given_name": patient.given_name,
                    "preferred_name": patient.preferred_name,
                    "family_name": patient.family_name,
                    "date_of_birth": patient.date_of_birth,
                    "administrative_sex": patient.administrative_sex,
                },
            })
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="emergency.queue.viewed",
        resource_type="emergency_queue", resource_id=None,
    )
    db.commit()
    return results


@router.get("/visits/{visit_id}", response_model=EmergencyVisitDetailRead)
def get_emergency_visit(
    visit_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    visit = _get_visit(db, hospital_id=hospital_id, visit_id=visit_id)
    _require_visit_read(db, user_id=user.id, hospital_id=hospital_id, visit=visit)
    result = _visit_detail(db, visit)
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="emergency.visit.viewed",
        resource_type="emergency_visit", resource_id=visit.id,
    )
    db.commit()
    return result


@router.post("/visits/{visit_id}/triage", response_model=EmergencyVisitDetailRead)
def record_emergency_triage(
    visit_id: UUID,
    payload: EmergencyTriageCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    visit = _get_visit(db, hospital_id=hospital_id, visit_id=visit_id, lock=True)
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_EMERGENCY_NURSE_ROLES,
        department_id=visit.department_id,
        allow_admin=False,
    )
    if visit.status not in {"arrived", "waiting", "in_treatment"}:
        raise HTTPException(status_code=409, detail={"code": "emergency_visit_not_triage_eligible"})
    if visit.status == "in_treatment" and not _has_assignment(
        db, user_id=user.id, hospital_id=hospital_id, visit=visit
    ):
        raise HTTPException(status_code=404, detail={"code": "assigned_emergency_visit_not_found"})
    latest_revision = db.scalar(select(func.max(EmergencyTriageAssessment.revision)).where(
        EmergencyTriageAssessment.hospital_id == hospital_id,
        EmergencyTriageAssessment.visit_id == visit.id,
    )) or 0
    now = datetime.now(timezone.utc)
    triage = EmergencyTriageAssessment(
        hospital_id=hospital_id,
        visit_id=visit.id,
        revision=latest_revision + 1,
        assessed_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(triage)
    visit.priority = payload.triage_level
    visit.triaged_at = now
    if visit.status == "arrived":
        visit.status = "waiting"
    _ensure_assignment(
        db, user_id=user.id, hospital_id=hospital_id,
        visit=visit, reason="Emergency triage assignment", now=now,
    )
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="emergency.visit.triaged",
        resource_type="emergency_visit", resource_id=visit.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(visit)
    return _visit_detail(db, visit)


@router.post("/visits/{visit_id}/take", response_model=EmergencyVisitRead)
def take_emergency_case(
    visit_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> EmergencyVisit:
    user, hospital_id = context
    visit = _get_visit(db, hospital_id=hospital_id, visit_id=visit_id, lock=True)
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES, department_id=visit.department_id,
        allow_admin=False,
    )
    if visit.status != "waiting":
        raise HTTPException(status_code=409, detail={"code": "emergency_visit_not_waiting"})
    if visit.assigned_clinician_user_id is not None and visit.assigned_clinician_user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "emergency_visit_assigned_to_another_clinician"})
    now = datetime.now(timezone.utc)
    visit.assigned_clinician_user_id = user.id
    visit.status = "in_treatment"
    visit.treatment_started_at = now
    _ensure_assignment(
        db, user_id=user.id, hospital_id=hospital_id,
        visit=visit, reason="Emergency clinician assignment", now=now,
    )
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="emergency.treatment.started",
        resource_type="emergency_visit", resource_id=visit.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(visit)
    return visit


@router.post("/visits/{visit_id}/events", response_model=EmergencyCareEventRead, status_code=status.HTTP_201_CREATED)
def record_emergency_care_event(
    visit_id: UUID,
    payload: EmergencyCareEventCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> EmergencyCareEvent:
    user, hospital_id = context
    visit = _get_visit(db, hospital_id=hospital_id, visit_id=visit_id)
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_EMERGENCY_NURSE_ROLES | _CLINICIAN_ROLES,
        department_id=visit.department_id,
        allow_admin=False,
    )
    if visit.status != "in_treatment" or not _has_assignment(
        db, user_id=user.id, hospital_id=hospital_id, visit=visit
    ):
        raise HTTPException(status_code=403, detail={"code": "active_emergency_care_assignment_required"})
    event = EmergencyCareEvent(
        hospital_id=hospital_id,
        visit_id=visit.id,
        performed_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(event)
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="emergency.care_event.recorded",
        resource_type="emergency_care_event", resource_id=event.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(event)
    return event


@router.post("/visits/{visit_id}/notes", response_model=EmergencyNoteRead, status_code=status.HTTP_201_CREATED)
def create_emergency_note(
    visit_id: UUID,
    payload: EmergencyNoteCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> EmergencyNote:
    user, hospital_id = context
    visit = _get_visit(db, hospital_id=hospital_id, visit_id=visit_id)
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_EMERGENCY_NURSE_ROLES | _CLINICIAN_ROLES,
        department_id=visit.department_id,
        allow_admin=False,
    )
    if visit.status not in {"waiting", "in_treatment"} or not _has_assignment(
        db, user_id=user.id, hospital_id=hospital_id, visit=visit
    ):
        raise HTTPException(status_code=403, detail={"code": "active_emergency_care_assignment_required"})
    note = EmergencyNote(
        hospital_id=hospital_id,
        visit_id=visit.id,
        author_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(note)
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="emergency.note.signed",
        resource_type="emergency_note", resource_id=note.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(note)
    return note


@router.post("/visits/{visit_id}/disposition", response_model=EmergencyVisitRead)
def close_emergency_visit(
    visit_id: UUID,
    payload: EmergencyDispositionCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> EmergencyVisit:
    user, hospital_id = context
    visit = _get_visit(db, hospital_id=hospital_id, visit_id=visit_id, lock=True)
    _, role_name = _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_EMERGENCY_NURSE_ROLES | _CLINICIAN_ROLES,
        department_id=visit.department_id,
        allow_admin=False,
    )
    if payload.disposition == "left_without_being_seen":
        if role_name not in _EMERGENCY_NURSE_ROLES or visit.status not in {"arrived", "waiting"}:
            raise HTTPException(status_code=409, detail={"code": "emergency_visit_cannot_leave_unseen"})
        visit.status = "left_without_being_seen"
        encounter_status = "left_without_being_seen"
    else:
        if (
            role_name not in _CLINICIAN_ROLES
            or visit.status != "in_treatment"
            or not _has_assignment(db, user_id=user.id, hospital_id=hospital_id, visit=visit)
        ):
            raise HTTPException(status_code=403, detail={"code": "assigned_emergency_clinician_required"})
        visit.status = "closed"
        encounter_status = {
            "discharged": "completed",
            "admission_requested": "admission_requested",
            "referred": "referred",
            "transfer_requested": "transfer_requested",
        }[payload.disposition]

    now = datetime.now(timezone.utc)
    visit.disposition = payload.disposition
    visit.disposition_note = payload.note
    visit.completed_at = now
    visit.closed_by_user_id = user.id
    visit.closed_at = now
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == visit.encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is not None:
        encounter.status = encounter_status
        encounter.ended_at = now
    assignments = db.scalars(select(PatientCareAssignment).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.encounter_id == visit.encounter_id,
        PatientCareAssignment.status == "active",
    ).with_for_update()).all()
    for assignment in assignments:
        assignment.valid_until = now + timedelta(hours=24)
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="emergency.visit.closed",
        resource_type="emergency_visit", resource_id=visit.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(visit)
    return visit
