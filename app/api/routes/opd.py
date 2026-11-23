import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    ClinicalConcept,
    Department,
    Encounter,
    HospitalMembership,
    MedicalKnowledgeDocument,
    MedicalKnowledgeSource,
    OPDConsultationNote,
    OPDDiagnosis,
    OPDTriageAssessment,
    OPDVisit,
    Patient,
    PatientCareAssignment,
    Role,
)
from app.schemas.opd import (
    OPDConsultationComplete,
    OPDDispositionCreate,
    OPDDiagnosisCreate,
    OPDVisitCreate,
    OPDVisitDetailRead,
    OPDQueueItemRead,
    OPDVisitRead,
    OPDTriageCreate,
)

router = APIRouter(prefix="/opd", tags=["outpatient department"])

_REGISTRATION_ROLES = {
    "registration_clerk", "receptionist", "medical_records_officer",
    "hospital_admin", "hospital_director", "system_admin",
}
_TRIAGE_ROLES = {
    "nurse", "triage_nurse", "emergency_nurse", "medical_officer",
    "doctor", "physician",
}
_CLINICIAN_ROLES = {
    "doctor", "physician", "medical_officer", "clinician",
    "pediatrician", "surgeon", "midwife",
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
        raise HTTPException(status_code=403, detail={"code": "opd_role_not_authorized"})
    if role_name not in _ADMIN_ROLES and department_id is not None:
        if membership.department_id != department_id:
            raise HTTPException(status_code=403, detail={"code": "opd_department_scope_required"})
    return membership, role_name


def _get_visit(db: Session, *, visit_id: UUID, hospital_id: UUID, lock: bool = False) -> OPDVisit:
    query = select(OPDVisit).where(
        OPDVisit.id == visit_id,
        OPDVisit.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    visit = db.scalar(query)
    if visit is None:
        raise HTTPException(status_code=404, detail={"code": "opd_visit_not_found"})
    return visit


def _has_active_assignment(
    db: Session,
    *,
    user_id: UUID,
    hospital_id: UUID,
    visit: OPDVisit,
    department_id: UUID | None = None,
) -> bool:
    now = datetime.now(timezone.utc)
    conditions = [
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == visit.patient_id,
        PatientCareAssignment.encounter_id == visit.encounter_id,
        PatientCareAssignment.staff_user_id == user_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ]
    if department_id is not None:
        conditions.append(PatientCareAssignment.department_id == department_id)
    return db.scalar(select(PatientCareAssignment.id).where(*conditions).limit(1)) is not None


def _ensure_assignment(
    db: Session,
    *,
    user_id: UUID,
    assigned_by_user_id: UUID,
    hospital_id: UUID,
    visit: OPDVisit,
    reason: str,
    now: datetime,
) -> None:
    if _has_active_assignment(
        db, user_id=user_id, hospital_id=hospital_id, visit=visit,
        department_id=visit.department_id,
    ):
        return
    db.add(PatientCareAssignment(
        hospital_id=hospital_id,
        patient_id=visit.patient_id,
        staff_user_id=user_id,
        assigned_by_user_id=assigned_by_user_id,
        department_id=visit.department_id,
        encounter_id=visit.encounter_id,
        assignment_reason=reason,
        status="active",
        valid_from=now,
    ))


def _require_visit_read(
    db: Session, *, user_id: UUID, hospital_id: UUID, visit: OPDVisit
) -> str:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if role_name in _REGISTRATION_ROLES | _ADMIN_ROLES:
        return role_name
    if role_name in _TRIAGE_ROLES and membership.department_id == visit.department_id and visit.status in {
        "registered", "arrived", "waiting"
    }:
        return role_name
    if role_name not in _TRIAGE_ROLES | _CLINICIAN_ROLES:
        raise HTTPException(status_code=403, detail={"code": "opd_read_role_required"})
    if membership.department_id != visit.department_id or not _has_active_assignment(
        db, user_id=user_id, hospital_id=hospital_id, visit=visit,
        department_id=membership.department_id,
    ):
        raise HTTPException(status_code=404, detail={"code": "opd_visit_not_found"})
    return role_name


def _visit_detail(db: Session, visit: OPDVisit) -> dict:
    triage = db.scalar(select(OPDTriageAssessment).where(
        OPDTriageAssessment.hospital_id == visit.hospital_id,
        OPDTriageAssessment.visit_id == visit.id,
    ))
    consultation = db.scalar(select(OPDConsultationNote).where(
        OPDConsultationNote.hospital_id == visit.hospital_id,
        OPDConsultationNote.visit_id == visit.id,
    ))
    diagnoses = db.scalars(select(OPDDiagnosis).where(
        OPDDiagnosis.hospital_id == visit.hospital_id,
        OPDDiagnosis.visit_id == visit.id,
    ).order_by(OPDDiagnosis.recorded_at)).all()
    patient = db.scalar(select(Patient).where(
        Patient.id == visit.patient_id, Patient.hospital_id == visit.hospital_id
    ))
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
        "triage": triage,
        "consultation": consultation,
        "diagnoses": diagnoses,
    }


@router.post("/visits", response_model=OPDVisitRead, status_code=status.HTTP_201_CREATED)
def create_opd_visit(
    payload: OPDVisitCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> OPDVisit:
    user, hospital_id = context
    membership, role_name = _require_role(
        db,
        user_id=user.id,
        hospital_id=hospital_id,
        allowed=_REGISTRATION_ROLES | _TRIAGE_ROLES | _CLINICIAN_ROLES,
    )
    patient = db.scalar(select(Patient).where(
        Patient.id == payload.patient_id, Patient.hospital_id == hospital_id
    ))
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
        raise HTTPException(status_code=404, detail={"code": "opd_department_not_found"})
    if role_name not in _REGISTRATION_ROLES | _ADMIN_ROLES and membership.department_id != department.id:
        raise HTTPException(status_code=403, detail={"code": "opd_department_scope_required"})

    now = datetime.now(timezone.utc)
    encounter = Encounter(
        hospital_id=hospital_id,
        patient_id=patient.id,
        department_id=department.id,
        encounter_type="opd",
        status="in_progress",
        chief_complaint=payload.chief_complaint.strip(),
        started_at=now,
    )
    db.add(encounter)
    db.flush()
    visit = OPDVisit(
        hospital_id=hospital_id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        department_id=department.id,
        visit_date=date.today(),
        queue_token=secrets.token_hex(4).upper(),
        visit_type=payload.visit_type,
        status="registered",
        priority="standard",
        assigned_clinician_user_id=payload.assigned_clinician_user_id,
        created_by_user_id=user.id,
    )
    db.add(visit)
    if payload.assigned_clinician_user_id is not None:
        clinician_membership = _membership(
            db, user_id=payload.assigned_clinician_user_id, hospital_id=hospital_id
        )
        clinician_role = _role_name(db, clinician_membership)
        if (
            clinician_membership is None
            or clinician_role not in _CLINICIAN_ROLES
            or clinician_membership.department_id != department.id
        ):
            db.rollback()
            raise HTTPException(status_code=422, detail={"code": "assigned_clinician_not_valid_for_department"})
        db.add(PatientCareAssignment(
            hospital_id=hospital_id,
            patient_id=patient.id,
            staff_user_id=payload.assigned_clinician_user_id,
            assigned_by_user_id=user.id,
            department_id=department.id,
            encounter_id=encounter.id,
            assignment_reason="OPD visit clinician assignment",
            status="active",
            valid_from=now,
        ))
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="opd.visit.registered", resource_type="opd_visit",
        resource_id=str(visit.id),
        metadata={"visit_type": visit.visit_type, "department_id": str(department.id)},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "opd_queue_token_collision_retry"}) from None
    db.refresh(visit)
    return visit


@router.get("/visits", response_model=list[OPDQueueItemRead])
def list_opd_visits(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    visit_status: str | None = Query(default=None, alias="status", max_length=32),
    department_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[OPDVisit]:
    user, hospital_id = context
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if role_name not in _REGISTRATION_ROLES | _ADMIN_ROLES | _TRIAGE_ROLES | _CLINICIAN_ROLES:
        raise HTTPException(status_code=403, detail={"code": "opd_read_role_required"})
    query = select(OPDVisit).where(OPDVisit.hospital_id == hospital_id)
    if department_id is not None:
        query = query.where(OPDVisit.department_id == department_id)
    if visit_status is not None:
        query = query.where(OPDVisit.status == visit_status)
    if role_name not in _REGISTRATION_ROLES | _ADMIN_ROLES:
        if membership.department_id is None:
            raise HTTPException(status_code=403, detail={"code": "opd_department_scope_required"})
        now = datetime.now(timezone.utc)
        query = query.where(OPDVisit.department_id == membership.department_id)
        if role_name in _CLINICIAN_ROLES:
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
            query = query.where(OPDVisit.encounter_id.in_(assigned_encounters))
        else:
            query = query.where(OPDVisit.status.in_(("registered", "arrived", "waiting")))
    visits = list(db.scalars(
        query.order_by(OPDVisit.visit_date.desc(), OPDVisit.created_at.desc())
        .limit(limit).offset(offset)
    ).all())
    queue_items = []
    for visit in visits:
        patient = db.scalar(select(Patient).where(
            Patient.id == visit.patient_id, Patient.hospital_id == hospital_id
        ))
        if patient is not None:
            queue_items.append({
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
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="opd.queue.viewed", resource_type="opd_queue",
        metadata={"returned_count": len(queue_items), "status_filter": visit_status},
    )
    db.commit()
    return queue_items


@router.get("/visits/{visit_id}", response_model=OPDVisitDetailRead)
def get_opd_visit(
    visit_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    visit = _get_visit(db, visit_id=visit_id, hospital_id=hospital_id)
    _require_visit_read(db, user_id=user.id, hospital_id=hospital_id, visit=visit)
    result = _visit_detail(db, visit)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="opd.visit.read", resource_type="opd_visit",
        resource_id=str(visit.id),
    )
    db.commit()
    return result


@router.post("/visits/{visit_id}/arrive", response_model=OPDVisitRead)
def mark_opd_arrival(
    visit_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> OPDVisit:
    user, hospital_id = context
    visit = _get_visit(db, visit_id=visit_id, hospital_id=hospital_id, lock=True)
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_REGISTRATION_ROLES | _TRIAGE_ROLES,
    )
    if role_name if False else False:
        pass
    if visit.status != "registered":
        raise HTTPException(status_code=409, detail={"code": "opd_visit_not_registered"})
    visit.status = "arrived"
    visit.arrival_at = datetime.now(timezone.utc)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="opd.visit.arrived", resource_type="opd_visit", resource_id=str(visit.id),
    )
    db.commit()
    db.refresh(visit)
    return visit


@router.post("/visits/{visit_id}/triage", response_model=OPDVisitDetailRead)
def record_opd_triage(
    visit_id: UUID,
    payload: OPDTriageCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    visit = _get_visit(db, visit_id=visit_id, hospital_id=hospital_id, lock=True)
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_TRIAGE_ROLES, department_id=visit.department_id, allow_admin=False,
    )
    if visit.status != "arrived":
        raise HTTPException(status_code=409, detail={"code": "opd_visit_must_be_arrived_for_triage"})
    now = datetime.now(timezone.utc)
    triage = OPDTriageAssessment(
        hospital_id=hospital_id,
        visit_id=visit.id,
        assessed_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(triage)
    visit.triage_at = now
    visit.priority = payload.triage_level
    visit.status = "waiting"
    _ensure_assignment(
        db, user_id=user.id, assigned_by_user_id=user.id,
        hospital_id=hospital_id, visit=visit,
        reason="OPD triage assessment", now=now,
    )
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="opd.visit.triaged", resource_type="opd_visit",
        resource_id=str(visit.id),
        metadata={
            "triage_level": payload.triage_level,
            "red_flag_present": payload.red_flag_present,
        },
    )
    db.commit()
    db.refresh(visit)
    return _visit_detail(db, visit)


@router.post("/visits/{visit_id}/consultation/start", response_model=OPDVisitRead)
def start_opd_consultation(
    visit_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> OPDVisit:
    user, hospital_id = context
    visit = _get_visit(db, visit_id=visit_id, hospital_id=hospital_id, lock=True)
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES, department_id=visit.department_id, allow_admin=False,
    )
    if visit.status != "waiting":
        raise HTTPException(status_code=409, detail={"code": "opd_visit_not_waiting"})
    if (
        visit.assigned_clinician_user_id is not None
        and visit.assigned_clinician_user_id != user.id
    ):
        raise HTTPException(status_code=403, detail={"code": "opd_visit_assigned_to_another_clinician"})
    now = datetime.now(timezone.utc)
    visit.assigned_clinician_user_id = user.id
    visit.status = "in_consultation"
    visit.consultation_started_at = now
    _ensure_assignment(
        db, user_id=user.id, assigned_by_user_id=user.id,
        hospital_id=hospital_id, visit=visit,
        reason="OPD consultation assignment", now=now,
    )
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="opd.consultation.started", resource_type="opd_visit",
        resource_id=str(visit.id),
    )
    db.commit()
    db.refresh(visit)
    return visit


@router.post("/visits/{visit_id}/consultation/complete", response_model=OPDVisitDetailRead)
def complete_opd_consultation(
    visit_id: UUID,
    payload: OPDConsultationComplete,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    visit = _get_visit(db, visit_id=visit_id, hospital_id=hospital_id, lock=True)
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES, department_id=visit.department_id, allow_admin=False,
    )
    if (
        visit.status != "in_consultation"
        or visit.assigned_clinician_user_id != user.id
        or not _has_active_assignment(
            db, user_id=user.id, hospital_id=hospital_id, visit=visit,
            department_id=visit.department_id,
        )
    ):
        raise HTTPException(status_code=409, detail={"code": "opd_consultation_not_owned_or_started"})
    existing = db.scalar(select(OPDConsultationNote.id).where(
        OPDConsultationNote.hospital_id == hospital_id,
        OPDConsultationNote.visit_id == visit.id,
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "opd_consultation_already_signed"})
    note = OPDConsultationNote(
        hospital_id=hospital_id,
        visit_id=visit.id,
        clinician_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(note)
    now = datetime.now(timezone.utc)
    visit.status = "completed"
    visit.completed_at = now
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="opd.consultation.signed", resource_type="opd_visit",
        resource_id=str(visit.id),
    )
    db.commit()
    db.refresh(visit)
    return _visit_detail(db, visit)


@router.post("/visits/{visit_id}/diagnoses", response_model=OPDDiagnosisRead, status_code=status.HTTP_201_CREATED)
def add_opd_diagnosis(
    visit_id: UUID,
    payload: OPDDiagnosisCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> OPDDiagnosis:
    user, hospital_id = context
    visit = _get_visit(db, visit_id=visit_id, hospital_id=hospital_id, lock=True)
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES, department_id=visit.department_id, allow_admin=False,
    )
    if (
        visit.status != "in_consultation"
        or visit.assigned_clinician_user_id != user.id
        or not _has_active_assignment(
            db, user_id=user.id, hospital_id=hospital_id, visit=visit,
            department_id=visit.department_id,
        )
    ):
        raise HTTPException(status_code=409, detail={"code": "opd_diagnosis_requires_active_consultation"})
    if payload.concept_id is not None:
        now = datetime.now(timezone.utc)
        concept = db.scalar(
            select(ClinicalConcept)
            .join(MedicalKnowledgeDocument, ClinicalConcept.document_id == MedicalKnowledgeDocument.id)
            .join(MedicalKnowledgeSource, MedicalKnowledgeDocument.source_id == MedicalKnowledgeSource.id)
            .where(
                ClinicalConcept.id == payload.concept_id,
                MedicalKnowledgeDocument.status == "approved",
                MedicalKnowledgeDocument.next_review_at.is_not(None),
                MedicalKnowledgeDocument.next_review_at > now,
                or_(MedicalKnowledgeDocument.effective_from.is_(None), MedicalKnowledgeDocument.effective_from <= now),
                or_(MedicalKnowledgeDocument.effective_to.is_(None), MedicalKnowledgeDocument.effective_to > now),
                MedicalKnowledgeSource.status == "active",
                or_(
                    MedicalKnowledgeSource.scope == "global",
                    and_(
                        MedicalKnowledgeSource.scope == "hospital",
                        MedicalKnowledgeSource.hospital_id == hospital_id,
                    ),
                ),
            )
        )
        if concept is None:
            raise HTTPException(status_code=422, detail={"code": "diagnosis_concept_not_approved_or_current"})
    if payload.is_primary:
        existing_primary = db.scalar(select(OPDDiagnosis.id).where(
            OPDDiagnosis.hospital_id == hospital_id,
            OPDDiagnosis.visit_id == visit.id,
            OPDDiagnosis.is_primary.is_(True),
        ))
        if existing_primary is not None:
            raise HTTPException(status_code=409, detail={"code": "opd_primary_diagnosis_already_exists"})
    diagnosis = OPDDiagnosis(
        hospital_id=hospital_id,
        visit_id=visit.id,
        recorded_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(diagnosis)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="opd.diagnosis.recorded", resource_type="opd_visit",
        resource_id=str(visit.id),
        metadata={"certainty": payload.certainty, "is_primary": payload.is_primary, "coded": payload.concept_id is not None},
    )
    db.commit()
    db.refresh(diagnosis)
    return diagnosis


@router.post("/visits/{visit_id}/disposition", response_model=OPDVisitRead)
def close_opd_visit(
    visit_id: UUID,
    payload: OPDDispositionCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> OPDVisit:
    user, hospital_id = context
    visit = _get_visit(db, visit_id=visit_id, hospital_id=hospital_id, lock=True)
    role_allowed = _CLINICIAN_ROLES | _TRIAGE_ROLES
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=role_allowed, department_id=visit.department_id, allow_admin=False,
    )
    if payload.disposition == "left_without_being_seen":
        if visit.status not in {"arrived", "waiting"}:
            raise HTTPException(status_code=409, detail={"code": "opd_visit_cannot_leave_unseen"})
        if role_allowed and _role_name(db, _membership(db, user_id=user.id, hospital_id=hospital_id)) not in _TRIAGE_ROLES | _CLINICIAN_ROLES:
            raise HTTPException(status_code=403, detail={"code": "opd_disposition_role_required"})
        visit.status = "left_without_being_seen"
    else:
        if visit.status != "completed":
            raise HTTPException(status_code=409, detail={"code": "opd_consultation_must_be_completed_before_disposition"})
        if visit.assigned_clinician_user_id != user.id:
            raise HTTPException(status_code=403, detail={"code": "opd_disposition_requires_assigned_clinician"})
        visit.status = "closed"

    now = datetime.now(timezone.utc)
    visit.disposition = payload.disposition
    visit.disposition_note = payload.note.strip()
    visit.closed_by_user_id = user.id
    visit.closed_at = now
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == visit.encounter_id, Encounter.hospital_id == hospital_id
    ).with_for_update())
    if encounter is not None:
        encounter.status = {
            "discharged": "completed",
            "admission_requested": "admission_requested",
            "referred": "referred",
            "transfer_requested": "transfer_requested",
            "left_without_being_seen": "left_without_being_seen",
        }[payload.disposition]
        encounter.ended_at = now

    assignments = db.scalars(select(PatientCareAssignment).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.encounter_id == visit.encounter_id,
        PatientCareAssignment.status == "active",
    ).with_for_update()).all()
    for assignment in assignments:
        assignment.valid_until = now + timedelta(hours=24)

    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="opd.visit.closed", resource_type="opd_visit",
        resource_id=str(visit.id),
        metadata={"disposition": payload.disposition},
    )
    db.commit()
    db.refresh(visit)
    return visit


@router.post("/visits/{visit_id}/cancel", response_model=OPDVisitRead)
def cancel_opd_visit(
    visit_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> OPDVisit:
    user, hospital_id = context
    visit = _get_visit(db, visit_id=visit_id, hospital_id=hospital_id, lock=True)
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_REGISTRATION_ROLES, department_id=visit.department_id,
    )
    if visit.status != "registered":
        raise HTTPException(status_code=409, detail={"code": "only_registered_opd_visit_can_be_cancelled"})
    now = datetime.now(timezone.utc)
    visit.status = "cancelled"
    visit.disposition_note = "Cancelled before arrival"
    visit.closed_by_user_id = user.id
    visit.closed_at = now
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == visit.encounter_id, Encounter.hospital_id == hospital_id
    ))
    if encounter is not None:
        encounter.status = "cancelled"
        encounter.ended_at = now
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="opd.visit.cancelled", resource_type="opd_visit",
        resource_id=str(visit.id),
    )
    db.commit()
    db.refresh(visit)
    return visit
