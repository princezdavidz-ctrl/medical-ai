from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import Department, Encounter, HospitalMembership, Patient, PatientConsent, Role, User
from app.models.hr import EmployeeProfile
from app.models.staff_portal import ClinicalStaffProfile, PatientCareTeamAssignment
from app.models.staff_scheduling import StaffShiftAssignment
from app.models.telemedicine import TelemedicineClinicalNote, TelemedicineEvent, TelemedicineSession
from app.schemas.telemedicine import (
    TelemedicineCancel, TelemedicineNoteCreate, TelemedicineNoteRead,
    TelemedicinePatientReady, TelemedicineSessionCreate, TelemedicineSessionRead,
)
from app.services.patient_authorization import has_active_patient_authorization

router = APIRouter(prefix="/telemedicine", tags=["telemedicine and remote care"])
_SCHEDULER_ROLES = {"telemedicine_coordinator", "appointment_scheduler", "hospital_admin", "hospital_director", "department_head", "nurse_manager"}
_PROVIDER_ROLES = {"physician", "clinical_officer", "nurse", "midwife", "therapist", "dentist", "pharmacist"}


def _role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    membership = db.scalar(select(HospitalMembership).join(
        Role, Role.id == HospitalMembership.role_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _require_scheduler(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    role = _role(db, user_id, hospital_id)
    if role not in _SCHEDULER_ROLES:
        raise HTTPException(status_code=403, detail={"code": "telemedicine_scheduler_role_required"})
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "active_user_account_required"})
    if role not in {"hospital_admin", "hospital_director"}:
        employee = db.scalar(select(EmployeeProfile).where(
            EmployeeProfile.hospital_id == hospital_id,
            EmployeeProfile.user_id == user_id,
            EmployeeProfile.employment_status == "active",
        ))
        if employee is None:
            raise HTTPException(status_code=403, detail={"code": "active_scheduler_employment_required"})
    return role


def _manager_department(db: Session, user_id: UUID, hospital_id: UUID, role: str) -> UUID | None:
    if role not in {"department_head", "nurse_manager"}:
        return None
    employee = db.scalar(select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id,
        EmployeeProfile.user_id == user_id,
        EmployeeProfile.employment_status == "active",
    ))
    if employee is None or employee.department_id is None:
        raise HTTPException(status_code=403, detail={"code": "active_manager_department_required"})
    return employee.department_id


def _enforce_department_scope(manager_department_id: UUID | None, target_department_id: UUID) -> None:
    if manager_department_id is not None and target_department_id != manager_department_id:
        raise HTTPException(status_code=403, detail={"code": "telemedicine_department_scope_denied"})


def _patient(db: Session, hospital_id: UUID, patient_id: UUID, lock: bool = False) -> Patient:
    query = select(Patient).where(Patient.hospital_id == hospital_id, Patient.id == patient_id)
    if lock:
        query = query.with_for_update()
    patient = db.scalar(query)
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    return patient


def _active_clinician(db: Session, hospital_id: UUID, clinician_user_id: UUID, lock: bool = False):
    employee_query = select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id,
        EmployeeProfile.user_id == clinician_user_id,
        EmployeeProfile.employment_status == "active",
    )
    if lock:
        employee_query = employee_query.with_for_update()
    employee = db.scalar(employee_query)
    membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == clinician_user_id,
        HospitalMembership.status == "active",
    ))
    profile = db.scalar(select(ClinicalStaffProfile).where(
        ClinicalStaffProfile.hospital_id == hospital_id,
        ClinicalStaffProfile.user_id == clinician_user_id,
        ClinicalStaffProfile.status == "verified",
    ))
    user = db.get(User, clinician_user_id)
    now = datetime.now(timezone.utc)
    if (
        employee is None or membership is None or profile is None or user is None
        or not user.is_active or profile.employee_profile_id != employee.id
        or (profile.license_expires_at is not None and profile.license_expires_at <= now)
    ):
        raise HTTPException(status_code=403, detail={"code": "active_verified_clinician_required"})
    return employee, profile


def _active_provider(db: Session, hospital_id: UUID, provider_user_id: UUID, lock: bool = False):
    employee, profile = _active_clinician(db, hospital_id, provider_user_id, lock=lock)
    if profile.clinical_role not in _PROVIDER_ROLES:
        raise HTTPException(status_code=403, detail={"code": "active_verified_telemedicine_provider_required"})
    return employee, profile

def _require_provider_shift_coverage(db: Session, hospital_id: UUID, employee_profile_id: UUID, department_id: UUID, starts_at: datetime, ends_at: datetime, lock: bool = False):
    query = select(StaffShiftAssignment).where(
        StaffShiftAssignment.hospital_id == hospital_id,
        StaffShiftAssignment.employee_profile_id == employee_profile_id,
        StaffShiftAssignment.status.in_(["scheduled", "confirmed"]),
        StaffShiftAssignment.starts_at <= starts_at,
        StaffShiftAssignment.ends_at >= ends_at,
        or_(StaffShiftAssignment.department_id == department_id, StaffShiftAssignment.department_id.is_(None)),
    ).order_by(StaffShiftAssignment.starts_at)
    if lock:
        query = query.with_for_update()
    shift = db.scalar(query)
    if shift is None:
        raise HTTPException(status_code=409, detail={"code": "provider_rostered_shift_covering_session_required"})
    return shift


def _active_telemedicine_consent(db: Session, hospital_id: UUID, patient_id: UUID, consent_id: UUID):
    now = datetime.now(timezone.utc)
    consent = db.scalar(select(PatientConsent).where(
        PatientConsent.hospital_id == hospital_id,
        PatientConsent.patient_id == patient_id,
        PatientConsent.id == consent_id,
    ))
    scope = consent.scope if consent is not None and isinstance(consent.scope, dict) else {}
    categories = scope.get("data_categories", [])
    permitted_uses = scope.get("permitted_uses", [])
    if (
        consent is None or consent.purpose != "telemedicine" or consent.status != "granted"
        or consent.basis_code is None or consent.granted_at is None or consent.granted_at > now
        or consent.withdrawn_at is not None
        or (consent.expires_at is not None and consent.expires_at <= now)
        or not isinstance(categories, list) or not isinstance(permitted_uses, list)
        or not all(isinstance(value, str) for value in categories + permitted_uses)
        or "clinical_records" not in categories
        or "telemedicine" not in permitted_uses
        or not has_active_patient_authorization(
            db, hospital_id=hospital_id, patient_id=patient_id,
            purpose="telemedicine", data_categories={"clinical_records"},
            permitted_use="telemedicine", now=now,
        )
    ):
        raise HTTPException(status_code=403, detail={"code": "active_telemedicine_consent_required"})
    return consent


def _require_care_team(db: Session, hospital_id: UUID, patient_id: UUID, provider_user_id: UUID):
    employee, _ = _active_clinician(db, hospital_id, provider_user_id)
    now = datetime.now(timezone.utc)
    assignment = db.scalar(select(PatientCareTeamAssignment).where(
        PatientCareTeamAssignment.hospital_id == hospital_id,
        PatientCareTeamAssignment.patient_id == patient_id,
        PatientCareTeamAssignment.staff_user_id == provider_user_id,
        PatientCareTeamAssignment.status == "active",
        PatientCareTeamAssignment.starts_at <= now,
        or_(PatientCareTeamAssignment.ends_at.is_(None), PatientCareTeamAssignment.ends_at > now),
    ))
    if (
        assignment is None or "encounters" not in (assignment.access_scope or [])
        or (assignment.department_id is not None and assignment.department_id != employee.department_id)
    ):
        raise HTTPException(status_code=403, detail={"code": "active_patient_care_team_assignment_required"})
    return assignment


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _event(db: Session, hospital_id: UUID, session: TelemedicineSession, user_id: UUID, event_type: str, metadata=None) -> None:
    db.add(TelemedicineEvent(
        hospital_id=hospital_id, session_id=session.id, patient_id=session.patient_id,
        actor_user_id=user_id, event_type=event_type,
        resource_type="telemedicine_session", resource_id=session.id,
        event_metadata=metadata or {},
    ))


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource_type: str, resource_id: UUID | None, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource_type, resource_id=str(resource_id) if resource_id is not None else None, metadata=metadata or {},
    )


def _session(db: Session, hospital_id: UUID, session_id: UUID, lock: bool = False):
    query = select(TelemedicineSession).where(
        TelemedicineSession.hospital_id == hospital_id,
        TelemedicineSession.id == session_id,
    )
    if lock:
        query = query.with_for_update()
    session = db.scalar(query)
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "telemedicine_session_not_found"})
    return session


def _require_session_access(db: Session, user_id: UUID, hospital_id: UUID, session: TelemedicineSession) -> None:
    role = _role(db, user_id, hospital_id)
    if role in _SCHEDULER_ROLES:
        manager_role = _require_scheduler(db, user_id, hospital_id)
        _enforce_department_scope(_manager_department(db, user_id, hospital_id, manager_role), session.department_id)
        return
    if session.provider_user_id == user_id:
        _active_provider(db, hospital_id, user_id)
        return
    _require_care_team(db, hospital_id, session.patient_id, user_id)


@router.post("/sessions", response_model=TelemedicineSessionRead, status_code=status.HTTP_201_CREATED)
def create_telemedicine_session(payload: TelemedicineSessionCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_scheduler(db, user.id, hospital_id)
    manager_department_id = _manager_department(db, user.id, hospital_id, role)
    _enforce_department_scope(manager_department_id, payload.department_id)
    now = datetime.now(timezone.utc)
    if payload.scheduled_start <= now or payload.scheduled_start > now + timedelta(days=365):
        raise HTTPException(status_code=422, detail={"code": "session_must_be_scheduled_within_next_365_days"})
    patient = _patient(db, hospital_id, payload.patient_id, lock=True)
    employee, profile = _active_provider(db, hospital_id, payload.provider_user_id, lock=True)
    department = db.scalar(select(Department).where(
        Department.hospital_id == hospital_id,
        Department.id == payload.department_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "active_department_not_found"})
    provider_membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == payload.provider_user_id,
        HospitalMembership.status == "active",
    ))
    if (
        employee.department_id not in (None, department.id)
        or (provider_membership is not None and provider_membership.department_id not in (None, department.id))
        or profile.employee_profile_id != employee.id
    ):
        raise HTTPException(status_code=403, detail={"code": "provider_department_scope_mismatch"})
    _require_provider_shift_coverage(db, hospital_id, employee.id, department.id, payload.scheduled_start, payload.scheduled_end)
    _active_telemedicine_consent(db, hospital_id, patient.id, payload.consent_id)
    conflict = db.scalar(select(TelemedicineSession.id).where(
        TelemedicineSession.hospital_id == hospital_id,
        TelemedicineSession.status.in_(["scheduled", "patient_ready", "in_progress"]),
        TelemedicineSession.scheduled_start < payload.scheduled_end,
        TelemedicineSession.scheduled_end > payload.scheduled_start,
        or_(
            TelemedicineSession.patient_id == patient.id,
            TelemedicineSession.provider_user_id == payload.provider_user_id,
        ),
    ).limit(1))
    if conflict is not None:
        raise HTTPException(status_code=409, detail={"code": "patient_or_provider_telemedicine_overlap"})
    session = TelemedicineSession(
        hospital_id=hospital_id, patient_id=patient.id,
        provider_employee_profile_id=employee.id, provider_user_id=payload.provider_user_id,
        department_id=department.id, consent_id=payload.consent_id,
        visit_reason=payload.visit_reason, scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end, status="scheduled",
        created_by_user_id=user.id,
    )
    db.add(session)
    db.flush()
    _event(db, hospital_id, session, user.id, "session_scheduled")
    _audit(db, hospital_id, user.id, "telemedicine.session_scheduled", "telemedicine_session", session.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(session)
    return session


@router.get("/sessions", response_model=list[TelemedicineSessionRead])
def list_telemedicine_sessions(
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    patient_id: UUID | None = None,
    provider_user_id: UUID | None = None,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    query = select(TelemedicineSession).where(TelemedicineSession.hospital_id == hospital_id)
    if role in _SCHEDULER_ROLES:
        manager_role = _require_scheduler(db, user.id, hospital_id)
        manager_department_id = _manager_department(db, user.id, hospital_id, manager_role)
        if manager_department_id is not None:
            query = query.where(TelemedicineSession.department_id == manager_department_id)
        if provider_user_id is not None:
            query = query.where(TelemedicineSession.provider_user_id == provider_user_id)
    else:
        _active_provider(db, hospital_id, user.id)
        query = query.where(TelemedicineSession.provider_user_id == user.id)
    if patient_id is not None:
        query = query.where(TelemedicineSession.patient_id == patient_id)
    for value in (start_at, end_at):
        if value is not None and value.tzinfo is None:
            raise HTTPException(status_code=422, detail={"code": "timezone_aware_session_filter_required"})
    if start_at is not None:
        query = query.where(TelemedicineSession.scheduled_start >= start_at)
    if end_at is not None:
        query = query.where(TelemedicineSession.scheduled_start <= end_at)
    rows = db.scalars(query.order_by(TelemedicineSession.scheduled_start).limit(300)).all()
    _audit(db, hospital_id, user.id, "telemedicine.session_list_viewed", "telemedicine_session_list", None, {"result_count": len(rows)})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return rows


@router.get("/sessions/{session_id}", response_model=TelemedicineSessionRead)
def get_telemedicine_session(session_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    session = _session(db, hospital_id, session_id)
    _require_session_access(db, user.id, hospital_id, session)
    _audit(db, hospital_id, user.id, "telemedicine.session_viewed", "telemedicine_session", session.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return session


@router.post("/sessions/{session_id}/patient-ready", response_model=TelemedicineSessionRead)
def mark_telemedicine_patient_ready(session_id: UUID, payload: TelemedicinePatientReady, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    session = _session(db, hospital_id, session_id, lock=True)
    role = _role(db, user.id, hospital_id)
    if role in _SCHEDULER_ROLES:
        manager_role = _require_scheduler(db, user.id, hospital_id)
        _enforce_department_scope(_manager_department(db, user.id, hospital_id, manager_role), session.department_id)
    elif session.provider_user_id == user.id:
        _active_provider(db, hospital_id, user.id)
    else:
        raise HTTPException(status_code=403, detail={"code": "assigned_provider_or_scheduler_required"})
    if session.status != "scheduled":
        raise HTTPException(status_code=409, detail={"code": "scheduled_telemedicine_session_required"})
    now = datetime.now(timezone.utc)
    if now < session.scheduled_start - timedelta(minutes=15) or now > session.scheduled_end + timedelta(minutes=15):
        raise HTTPException(status_code=409, detail={"code": "outside_telemedicine_patient_ready_window"})
    _active_telemedicine_consent(db, hospital_id, session.patient_id, session.consent_id)
    session.status = "patient_ready"
    session.patient_ready_at = now
    session.patient_ready_by_user_id = user.id
    session.patient_location_reference = payload.patient_location_reference
    session.emergency_contact_reference = payload.emergency_contact_reference
    session.safety_confirmed_at = now
    session.safety_confirmed_by_user_id = user.id
    session.patient_identity_confirmed = payload.patient_identity_confirmed
    session.privacy_confirmed = payload.privacy_confirmed
    session.emergency_plan_acknowledged = payload.emergency_plan_acknowledged
    _event(db, hospital_id, session, user.id, "patient_ready")
    _audit(db, hospital_id, user.id, "telemedicine.patient_ready", "telemedicine_session", session.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(session)
    return session


@router.post("/sessions/{session_id}/start", response_model=TelemedicineSessionRead)
def start_telemedicine_session(session_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    session = _session(db, hospital_id, session_id, lock=True)
    if session.provider_user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "assigned_provider_required"})
    employee, _ = _active_provider(db, hospital_id, user.id, lock=True)
    _require_provider_shift_coverage(db, hospital_id, employee.id, session.department_id, session.scheduled_start, session.scheduled_end)
    if session.status != "patient_ready":
        raise HTTPException(status_code=409, detail={"code": "patient_ready_session_required"})
    now = datetime.now(timezone.utc)
    if now < session.scheduled_start - timedelta(minutes=15) or now > session.scheduled_end + timedelta(minutes=15):
        raise HTTPException(status_code=409, detail={"code": "outside_telemedicine_start_window"})
    _active_telemedicine_consent(db, hospital_id, session.patient_id, session.consent_id)
    _require_care_team(db, hospital_id, session.patient_id, user.id)
    encounter = Encounter(
        hospital_id=hospital_id, patient_id=session.patient_id,
        department_id=session.department_id, encounter_type="telemedicine",
        status="in_progress", chief_complaint=session.visit_reason, started_at=now,
    )
    db.add(encounter)
    db.flush()
    session.encounter_id = encounter.id
    session.started_at = now
    session.started_by_user_id = user.id
    session.status = "in_progress"
    _event(db, hospital_id, session, user.id, "session_started")
    _audit(db, hospital_id, user.id, "telemedicine.session_started", "telemedicine_session", session.id, {"encounter_id": str(encounter.id)})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(session)
    return session


@router.post("/sessions/{session_id}/notes", response_model=TelemedicineNoteRead, status_code=status.HTTP_201_CREATED)
def create_telemedicine_note(session_id: UUID, payload: TelemedicineNoteCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    session = _session(db, hospital_id, session_id, lock=True)
    if session.provider_user_id != user.id or session.status != "in_progress" or session.encounter_id is None:
        raise HTTPException(status_code=403, detail={"code": "assigned_active_telemedicine_provider_required"})
    _active_provider(db, hospital_id, user.id)
    _require_care_team(db, hospital_id, session.patient_id, user.id)
    note = TelemedicineClinicalNote(
        hospital_id=hospital_id, session_id=session.id,
        encounter_id=session.encounter_id, patient_id=session.patient_id,
        author_user_id=user.id, note_type=payload.note_type,
        note_text=payload.note_text, signed_at=datetime.now(timezone.utc),
    )
    db.add(note)
    db.flush()
    _event(db, hospital_id, session, user.id, "note_signed", {"note_id": str(note.id), "note_type": note.note_type})
    _audit(db, hospital_id, user.id, "telemedicine.note_signed", "telemedicine_clinical_note", note.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(note)
    return note


@router.get("/sessions/{session_id}/notes", response_model=list[TelemedicineNoteRead])
def list_telemedicine_notes(session_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    session = _session(db, hospital_id, session_id)
    if session.provider_user_id == user.id:
        _active_provider(db, hospital_id, user.id)
        _require_care_team(db, hospital_id, session.patient_id, user.id)
    else:
        _require_care_team(db, hospital_id, session.patient_id, user.id)
    notes = db.scalars(select(TelemedicineClinicalNote).where(
        TelemedicineClinicalNote.hospital_id == hospital_id,
        TelemedicineClinicalNote.session_id == session.id,
        TelemedicineClinicalNote.patient_id == session.patient_id,
    ).order_by(TelemedicineClinicalNote.signed_at)).all()
    _audit(db, hospital_id, user.id, "telemedicine.notes_viewed", "telemedicine_session", session.id, {"note_count": len(notes)})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return notes


@router.post("/sessions/{session_id}/complete", response_model=TelemedicineSessionRead)
def complete_telemedicine_session(session_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    session = _session(db, hospital_id, session_id, lock=True)
    if session.provider_user_id != user.id or session.status != "in_progress" or session.encounter_id is None:
        raise HTTPException(status_code=403, detail={"code": "assigned_active_telemedicine_provider_required"})
    _active_provider(db, hospital_id, user.id)
    _require_care_team(db, hospital_id, session.patient_id, user.id)
    note_count = db.scalar(select(TelemedicineClinicalNote.id).where(
        TelemedicineClinicalNote.hospital_id == hospital_id,
        TelemedicineClinicalNote.session_id == session.id,
        TelemedicineClinicalNote.note_type.in_(["consultation", "assessment"]),
    ).limit(1))
    if note_count is None:
        raise HTTPException(status_code=409, detail={"code": "signed_consultation_or_assessment_note_required_before_completion"})
    now = datetime.now(timezone.utc)
    encounter = db.scalar(select(Encounter).where(
        Encounter.hospital_id == hospital_id,
        Encounter.id == session.encounter_id,
        Encounter.patient_id == session.patient_id,
    ).with_for_update())
    if encounter is None or encounter.status != "in_progress":
        raise HTTPException(status_code=409, detail={"code": "active_telemedicine_encounter_required"})
    encounter.status = "completed"
    encounter.ended_at = now
    session.status = "completed"
    session.ended_at = now
    session.ended_by_user_id = user.id
    _event(db, hospital_id, session, user.id, "session_completed")
    _audit(db, hospital_id, user.id, "telemedicine.session_completed", "telemedicine_session", session.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(session)
    return session


@router.post("/sessions/{session_id}/cancel", response_model=TelemedicineSessionRead)
def cancel_telemedicine_session(session_id: UUID, payload: TelemedicineCancel, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    session = _session(db, hospital_id, session_id, lock=True)
    role = _role(db, user.id, hospital_id)
    if role in _SCHEDULER_ROLES:
        manager_role = _require_scheduler(db, user.id, hospital_id)
        _enforce_department_scope(_manager_department(db, user.id, hospital_id, manager_role), session.department_id)
    elif session.provider_user_id == user.id:
        _active_provider(db, hospital_id, user.id)
    else:
        raise HTTPException(status_code=403, detail={"code": "assigned_provider_or_scheduler_required"})
    if session.status not in ("scheduled", "patient_ready"):
        raise HTTPException(status_code=409, detail={"code": "only_pre_start_sessions_can_be_cancelled"})
    session.status = "cancelled"
    session.cancelled_by_user_id = user.id
    session.cancelled_at = datetime.now(timezone.utc)
    session.cancellation_reason = payload.reason
    _event(db, hospital_id, session, user.id, "session_cancelled")
    _audit(db, hospital_id, user.id, "telemedicine.session_cancelled", "telemedicine_session", session.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(session)
    return session


@router.post("/sessions/{session_id}/no-show", response_model=TelemedicineSessionRead)
def mark_telemedicine_no_show(session_id: UUID, payload: TelemedicineCancel, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_scheduler(db, user.id, hospital_id)
    session = _session(db, hospital_id, session_id, lock=True)
    _enforce_department_scope(_manager_department(db, user.id, hospital_id, role), session.department_id)
    if session.status != "scheduled" or datetime.now(timezone.utc) <= session.scheduled_end:
        raise HTTPException(status_code=409, detail={"code": "scheduled_session_past_end_required_for_no_show"})
    session.status = "no_show"
    session.cancelled_by_user_id = user.id
    session.cancelled_at = datetime.now(timezone.utc)
    session.cancellation_reason = payload.reason
    _event(db, hospital_id, session, user.id, "session_no_show")
    _audit(db, hospital_id, user.id, "telemedicine.session_no_show", "telemedicine_session", session.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(session)
    return session
