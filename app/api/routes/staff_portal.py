from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    Department, Encounter, HospitalMembership, Patient, Role, User,
)
from app.models.hr import EmployeeProfile
from app.models.staff_portal import (
    ClinicalStaffProfile, PatientCareTeamAssignment, StaffWorkQueueTask, StaffPortalEvent,
)
from app.models.laboratory import LaboratoryOrder, LaboratorySpecimen, LaboratoryResult
from app.models.pharmacy import MedicationDefinition, MedicationOrder
from app.schemas.staff_portal import (
    ClinicalStaffProfileCreate, ClinicalStaffProfileRead, ClinicalStaffVerification,
    ClinicalStaffSuspension, ClinicalStaffReinstatement, CareTeamAssignmentCreate, CareTeamAssignmentRead,
    CareTeamAssignmentEnd, StaffTaskCreate, StaffTaskUpdate, StaffTaskRead,
)

router = APIRouter(prefix="/staff-portal", tags=["doctor and medical staff portal"])
_CLINICAL_ROLES = {
    "physician", "doctor", "medical_officer", "clinician", "nurse", "registered_nurse",
    "nursing_officer", "midwife", "pharmacist", "pharmacy_officer", "clinical_officer",
    "dentist", "therapist", "radiographer", "radiology_technician",
    "laboratory_scientist", "laboratory_technician", "lab_technician",
    "pediatrician", "surgeon", "emergency_physician",
}
_CLINICAL_ROLE_MATCH = {
    "physician": {"physician", "doctor", "medical_officer", "clinician", "pediatrician", "surgeon", "emergency_physician"},
    "nurse": {"nurse", "registered_nurse", "nursing_officer", "nurse_manager"},
    "midwife": {"midwife"},
    "pharmacist": {"pharmacist", "pharmacy_officer"},
    "clinical_officer": {"clinical_officer", "medical_officer", "clinician"},
    "dentist": {"dentist"},
    "therapist": {"therapist"},
    "radiographer": {"radiographer", "radiology_technician"},
    "laboratory_scientist": {"laboratory_scientist", "laboratory_technician", "lab_technician"},
    "other": _CLINICAL_ROLES,
}
_ADMIN_ROLES = {"hospital_admin", "hospital_owner", "medical_director", "hr_manager"}
_CLINICAL_ADMIN_ROLES = {"hospital_admin", "hospital_owner", "medical_director"}
_ASSIGNER_ROLES = _CLINICAL_ADMIN_ROLES | {"department_head", "department_manager", "physician", "doctor", "medical_officer", "clinician", "clinical_officer", "surgeon", "pediatrician", "midwife", "nurse_manager", "nursing_supervisor"}
_ALLOWED_PATIENT_SCOPES = {"profile", "encounters", "lab_results", "medications"}


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


def _require_role(db: Session, user_id: UUID, hospital_id: UUID, allowed: set[str]) -> str:
    role = _role(db, user_id, hospital_id)
    if role not in allowed:
        raise HTTPException(status_code=403, detail={"code": "staff_portal_role_not_authorized"})
    return role


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _event(db: Session, hospital_id: UUID, user_id: UUID, event_type: str, resource_type: str, resource_id: UUID | None, metadata=None) -> None:
    db.add(StaffPortalEvent(
        hospital_id=hospital_id, actor_user_id=user_id, event_type=event_type,
        resource_type=resource_type, resource_id=resource_id, event_metadata=metadata or {},
    ))


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource_type: str, resource_id: UUID | None, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource_type, resource_id=str(resource_id) if resource_id else None,
        metadata=metadata or {},
    )


def _employee_profile(db: Session, hospital_id: UUID, user_id: UUID):
    if _role(db, user_id, hospital_id) not in _CLINICAL_ROLES | _CLINICAL_ADMIN_ROLES | {"department_head", "nurse_manager"}:
        raise HTTPException(status_code=403, detail={"code": "active_clinical_staff_membership_required"})
    employee = db.scalar(select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id,
        EmployeeProfile.user_id == user_id,
        EmployeeProfile.employment_status == "active",
    ))
    if employee is None:
        raise HTTPException(status_code=403, detail={"code": "active_hospital_employee_profile_required"})
    return employee


def _verified_clinical_profile(db: Session, hospital_id: UUID, user_id: UUID):
    active_role = _role(db, user_id, hospital_id)
    if active_role not in _CLINICAL_ROLES:
        raise HTTPException(status_code=403, detail={"code": "active_clinical_membership_required"})
    profile = db.scalar(select(ClinicalStaffProfile).where(
        ClinicalStaffProfile.hospital_id == hospital_id,
        ClinicalStaffProfile.user_id == user_id,
        ClinicalStaffProfile.status == "verified",
    ))
    if profile is None or active_role not in _CLINICAL_ROLE_MATCH.get(profile.clinical_role, set()):
        raise HTTPException(status_code=403, detail={"code": "verified_matching_clinical_profile_required"})
    if profile.license_expires_at is not None and profile.license_expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail={"code": "clinical_license_expired"})
    return profile


def _care_assignment(db: Session, user_id: UUID, hospital_id: UUID, patient_id: UUID):
    _employee_profile(db, hospital_id, user_id)
    _verified_clinical_profile(db, hospital_id, user_id)
    now = datetime.now(timezone.utc)
    assignment = db.scalar(select(PatientCareTeamAssignment).where(
        PatientCareTeamAssignment.hospital_id == hospital_id,
        PatientCareTeamAssignment.patient_id == patient_id,
        PatientCareTeamAssignment.staff_user_id == user_id,
        PatientCareTeamAssignment.status == "active",
        PatientCareTeamAssignment.starts_at <= now,
        or_(PatientCareTeamAssignment.ends_at.is_(None), PatientCareTeamAssignment.ends_at > now),
    ))
    if assignment is None:
        raise HTTPException(status_code=403, detail={"code": "active_patient_care_team_assignment_required"})
    return assignment


@router.get("/me")
def get_staff_portal_me(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_role(db, user.id, hospital_id, _CLINICAL_ROLES | _CLINICAL_ADMIN_ROLES | {"department_head", "nurse_manager"})
    employee = db.scalar(select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id,
        EmployeeProfile.user_id == user.id,
    ))
    clinical = db.scalar(select(ClinicalStaffProfile).where(
        ClinicalStaffProfile.hospital_id == hospital_id,
        ClinicalStaffProfile.user_id == user.id,
    ))
    return {
        "user_id": user.id, "email": user.email, "hospital_id": hospital_id,
        "hospital_role": role, "employee_profile_id": employee.id if employee else None,
        "department_id": employee.department_id if employee else None,
        "employment_status": employee.employment_status if employee else None,
        "clinical_profile": ClinicalStaffProfileRead.model_validate(clinical) if clinical else None,
    }


@router.get("/clinical-profile", response_model=ClinicalStaffProfileRead)
def get_my_clinical_profile(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_role(db, user.id, hospital_id, _CLINICAL_ROLES)
    profile = db.scalar(select(ClinicalStaffProfile).where(
        ClinicalStaffProfile.hospital_id == hospital_id,
        ClinicalStaffProfile.user_id == user.id,
    ))
    if profile is None:
        raise HTTPException(status_code=404, detail={"code": "clinical_profile_not_submitted"})
    return profile


@router.post("/clinical-profile", response_model=ClinicalStaffProfileRead, status_code=status.HTTP_201_CREATED)
def submit_clinical_profile(payload: ClinicalStaffProfileCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_role(db, user.id, hospital_id, _CLINICAL_ROLES)
    employee = _employee_profile(db, hospital_id, user.id)
    if employee.id != payload.employee_profile_id:
        raise HTTPException(status_code=403, detail={"code": "clinical_profile_must_match_own_employee_record"})
    current_role = _role(db, user.id, hospital_id)
    if current_role not in _CLINICAL_ROLE_MATCH.get(payload.clinical_role, set()):
        raise HTTPException(status_code=422, detail={"code": "clinical_role_must_match_active_hospital_role"})
    if payload.license_expires_at is not None and (
        payload.license_expires_at.tzinfo is None or payload.license_expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=422, detail={"code": "license_expiry_must_be_future_and_timezone_aware"})
    profile = db.scalar(select(ClinicalStaffProfile).where(
        ClinicalStaffProfile.hospital_id == hospital_id,
        ClinicalStaffProfile.user_id == user.id,
    ).with_for_update())
    if profile is not None and profile.status == "suspended":
        raise HTTPException(status_code=409, detail={"code": "suspended_profile_requires_admin_reinstatement"})
    if profile is not None and profile.status == "verified" and (
        profile.license_expires_at is None or profile.license_expires_at > datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=409, detail={"code": "active_verified_profile_requires_admin_review"})
    if profile is None:
        profile = ClinicalStaffProfile(
            hospital_id=hospital_id, user_id=user.id, submitted_by_user_id=user.id,
            status="pending", **payload.model_dump(),
        )
        db.add(profile)
    else:
        for key, value in payload.model_dump().items():
            setattr(profile, key, value)
        profile.status = "pending"
        profile.evidence_reference = None
        profile.rejection_reason = None
        profile.suspension_reason = None
        profile.submitted_by_user_id = user.id
        profile.verified_by_user_id = None
        profile.verified_at = None
    try:
        db.flush()
        _event(db, hospital_id, user.id, "clinical_profile_submitted", "clinical_staff_profile", profile.id)
        _audit(db, hospital_id, user.id, "staff_portal.clinical_profile_submitted", "clinical_staff_profile", profile.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "clinical_registration_number_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(profile)
    return profile


@router.get("/clinical-profiles", response_model=list[ClinicalStaffProfileRead])
def list_clinical_profiles(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_role(db, user.id, hospital_id, _ADMIN_ROLES)
    return db.scalars(select(ClinicalStaffProfile).where(
        ClinicalStaffProfile.hospital_id == hospital_id,
    ).order_by(ClinicalStaffProfile.created_at.desc()).limit(300)).all()


@router.post("/clinical-profiles/{profile_id}/decision", response_model=ClinicalStaffProfileRead)
def decide_clinical_profile(profile_id: UUID, payload: ClinicalStaffVerification, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_role(db, user.id, hospital_id, _ADMIN_ROLES)
    profile = db.scalar(select(ClinicalStaffProfile).where(
        ClinicalStaffProfile.id == profile_id, ClinicalStaffProfile.hospital_id == hospital_id,
    ).with_for_update())
    if profile is None or profile.status not in ("pending", "rejected"):
        raise HTTPException(status_code=404, detail={"code": "pending_clinical_profile_not_found"})
    if profile.submitted_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_credential_verification_required"})
    if payload.decision == "verified":
        if not payload.evidence_reference:
            raise HTTPException(status_code=422, detail={"code": "credential_evidence_required"})
        if profile.license_expires_at is not None and profile.license_expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail={"code": "professional_license_expired"})
        profile.status = "verified"
        profile.evidence_reference = payload.evidence_reference
        profile.rejection_reason = None
        profile.verified_by_user_id = user.id
        profile.verified_at = datetime.now(timezone.utc)
        event_type = "clinical_profile_verified"
    else:
        if not payload.rejection_reason:
            raise HTTPException(status_code=422, detail={"code": "credential_rejection_reason_required"})
        profile.status = "rejected"
        profile.evidence_reference = None
        profile.rejection_reason = payload.rejection_reason
        profile.verified_by_user_id = None
        profile.verified_at = None
        event_type = "clinical_profile_rejected"
    _event(db, hospital_id, user.id, event_type, "clinical_staff_profile", profile.id)
    _audit(db, hospital_id, user.id, "staff_portal.clinical_profile_decided", "clinical_staff_profile", profile.id, {"decision": payload.decision})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(profile)
    return profile


@router.post("/clinical-profiles/{profile_id}/suspend", response_model=ClinicalStaffProfileRead)
def suspend_clinical_profile(profile_id: UUID, payload: ClinicalStaffSuspension, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_role(db, user.id, hospital_id, _ADMIN_ROLES)
    profile = db.scalar(select(ClinicalStaffProfile).where(
        ClinicalStaffProfile.id == profile_id, ClinicalStaffProfile.hospital_id == hospital_id,
    ).with_for_update())
    if profile is None or profile.status != "verified":
        raise HTTPException(status_code=404, detail={"code": "verified_clinical_profile_not_found"})
    profile.status = "suspended"
    profile.suspension_reason = payload.reason
    now = datetime.now(timezone.utc)
    active_assignments = db.scalars(select(PatientCareTeamAssignment).where(
        PatientCareTeamAssignment.hospital_id == hospital_id,
        PatientCareTeamAssignment.staff_user_id == profile.user_id,
        PatientCareTeamAssignment.status == "active",
    ).with_for_update()).all()
    for assignment in active_assignments:
        assignment.status = "revoked"
        assignment.ended_by_user_id = user.id
        assignment.ended_at = now
        assignment.end_reason = "Clinical credential suspended: " + payload.reason
        _event(db, hospital_id, user.id, "care_team_ended", "patient_care_team_assignment", assignment.id, {"status": "revoked", "reason": "clinical_profile_suspended"})
    _event(db, hospital_id, user.id, "clinical_profile_suspended", "clinical_staff_profile", profile.id)
    _audit(db, hospital_id, user.id, "staff_portal.clinical_profile_suspended", "clinical_staff_profile", profile.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(profile)
    return profile





@router.post("/clinical-profiles/{profile_id}/reinstate", response_model=ClinicalStaffProfileRead)
def reinstate_clinical_profile(profile_id: UUID, payload: ClinicalStaffReinstatement, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_role(db, user.id, hospital_id, _ADMIN_ROLES)
    profile = db.scalar(select(ClinicalStaffProfile).where(
        ClinicalStaffProfile.id == profile_id, ClinicalStaffProfile.hospital_id == hospital_id,
    ).with_for_update())
    if profile is None or profile.status != "suspended":
        raise HTTPException(status_code=404, detail={"code": "suspended_clinical_profile_not_found"})
    if user.id in (profile.submitted_by_user_id, profile.verified_by_user_id):
        raise HTTPException(status_code=409, detail={"code": "independent_reinstatement_review_required"})
    if profile.license_expires_at is not None and profile.license_expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail={"code": "professional_license_expired"})
    profile.status = "verified"
    profile.evidence_reference = payload.evidence_reference
    profile.suspension_reason = None
    profile.verified_by_user_id = user.id
    profile.verified_at = datetime.now(timezone.utc)
    _event(db, hospital_id, user.id, "clinical_profile_verified", "clinical_staff_profile", profile.id, {"reinstatement": True, "review_note": payload.review_note})
    _audit(db, hospital_id, user.id, "staff_portal.clinical_profile_reinstated", "clinical_staff_profile", profile.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(profile)
    return profile


@router.post("/care-team", response_model=CareTeamAssignmentRead, status_code=status.HTTP_201_CREATED)
def assign_patient_care_team(payload: CareTeamAssignmentCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_role(db, user.id, hospital_id, _ASSIGNER_ROLES)
    assigner_employee = None
    if role in _CLINICAL_ROLES:
        assigner_employee = _employee_profile(db, hospital_id, user.id)
        _verified_clinical_profile(db, hospital_id, user.id)
    elif role in {"department_head", "department_manager", "nurse_manager"}:
        assigner_employee = _employee_profile(db, hospital_id, user.id)
    if not set(payload.access_scope).issubset(_ALLOWED_PATIENT_SCOPES) or not payload.access_scope or len(set(payload.access_scope)) != len(payload.access_scope) or "profile" not in payload.access_scope:
        raise HTTPException(status_code=422, detail={"code": "invalid_patient_care_access_scope"})
    if payload.ends_at is not None and (payload.ends_at.tzinfo is None or payload.ends_at <= datetime.now(timezone.utc)):
        raise HTTPException(status_code=422, detail={"code": "care_assignment_end_must_be_future_and_timezone_aware"})
    if user.id == payload.staff_user_id:
        raise HTTPException(status_code=422, detail={"code": "self_care_assignment_not_allowed"})
    patient = db.scalar(select(Patient).where(
        Patient.id == payload.patient_id, Patient.hospital_id == hospital_id,
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    employee = _employee_profile(db, hospital_id, payload.staff_user_id)
    clinical = _verified_clinical_profile(db, hospital_id, payload.staff_user_id)
    target_department_id = payload.department_id or employee.department_id
    if target_department_id is not None:
        department = db.scalar(select(Department).where(
            Department.id == target_department_id, Department.hospital_id == hospital_id,
            Department.status == "active",
        ))
        if department is None:
            raise HTTPException(status_code=404, detail={"code": "active_department_not_found"})
        if employee.department_id is not None and employee.department_id != department.id:
            raise HTTPException(status_code=422, detail={"code": "staff_department_mismatch"})
    if role not in _CLINICAL_ADMIN_ROLES and assigner_employee is not None:
        if assigner_employee.department_id is None or assigner_employee.department_id != target_department_id:
            raise HTTPException(status_code=403, detail={"code": "care_team_assignment_department_scope_required"})
    role_compatibility = {
        "attending_physician": {"physician", "clinical_officer"},
        "consultant": {"physician", "clinical_officer"},
        "primary_nurse": {"nurse"},
        "midwife": {"midwife", "nurse"},
        "pharmacist": {"pharmacist"},
        "allied_health": {"dentist", "therapist", "radiographer", "laboratory_scientist", "other"},
        "case_manager": {"nurse", "clinical_officer", "physician", "other"},
        "other": set(_CLINICAL_ROLES) | {"other"},
    }
    if clinical.clinical_role not in role_compatibility[payload.care_role]:
        raise HTTPException(status_code=422, detail={"code": "clinical_role_not_compatible_with_care_assignment"})
    now = datetime.now(timezone.utc)
    expired_assignments = db.scalars(select(PatientCareTeamAssignment).where(
        PatientCareTeamAssignment.hospital_id == hospital_id,
        PatientCareTeamAssignment.patient_id == payload.patient_id,
        PatientCareTeamAssignment.staff_user_id == payload.staff_user_id,
        PatientCareTeamAssignment.care_role == payload.care_role,
        PatientCareTeamAssignment.status == "active",
        PatientCareTeamAssignment.ends_at <= now,
    ).with_for_update()).all()
    for expired in expired_assignments:
        expired.status = "ended"
        expired.ended_by_user_id = user.id
        expired.ended_at = now
        expired.end_reason = "Assignment expired before renewal"
        _event(db, hospital_id, user.id, "care_team_ended", "patient_care_team_assignment", expired.id, {"status": "ended", "reason": "expired"})
    assignment_values = payload.model_dump()
    assignment_values["department_id"] = target_department_id
    assignment = PatientCareTeamAssignment(
        hospital_id=hospital_id, assigned_by_user_id=user.id, status="active",
        **assignment_values,
    )
    db.add(assignment)
    try:
        db.flush()
        _event(db, hospital_id, user.id, "care_team_assigned", "patient_care_team_assignment", assignment.id, {"care_role": payload.care_role})
        _audit(db, hospital_id, user.id, "staff_portal.care_team_assigned", "patient_care_team_assignment", assignment.id, {"care_role": payload.care_role})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "active_care_team_assignment_already_exists"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(assignment)
    return assignment


@router.get("/patients")
def list_assigned_patients(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_role(db, user.id, hospital_id, _CLINICAL_ROLES)
    _employee_profile(db, hospital_id, user.id)
    _verified_clinical_profile(db, hospital_id, user.id)
    now = datetime.now(timezone.utc)
    rows = db.execute(select(PatientCareTeamAssignment, Patient).join(
        Patient, and_(Patient.id == PatientCareTeamAssignment.patient_id, Patient.hospital_id == PatientCareTeamAssignment.hospital_id),
    ).where(
        PatientCareTeamAssignment.hospital_id == hospital_id,
        PatientCareTeamAssignment.staff_user_id == user.id,
        PatientCareTeamAssignment.status == "active",
        PatientCareTeamAssignment.starts_at <= now,
        or_(PatientCareTeamAssignment.ends_at.is_(None), PatientCareTeamAssignment.ends_at > now),
    ).order_by(Patient.family_name, Patient.given_name)).all()
    result = []
    for assignment, patient in rows:
        if "profile" not in (assignment.access_scope or []):
            continue
        result.append({
            "patient_id": patient.id, "medical_record_number": patient.medical_record_number,
            "given_name": patient.given_name, "family_name": patient.family_name,
            "care_role": assignment.care_role, "access_scope": assignment.access_scope,
            "department_id": assignment.department_id, "assignment_id": assignment.id,
        })
        _event(db, hospital_id, user.id, "patient_overview_viewed", "patient", patient.id, {"action": "assigned_patient_list_viewed", "assignment_id": str(assignment.id)})
        _audit(db, hospital_id, user.id, "staff_portal.assigned_patient_list_viewed", "patient", patient.id)
    if result:
        db.commit()
        _restore_context(db, user.id, hospital_id)
    return result


@router.get("/patients/{patient_id}/overview")
def get_patient_clinical_overview(patient_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_role(db, user.id, hospital_id, _CLINICAL_ROLES)
    assignment = _care_assignment(db, user.id, hospital_id, patient_id)
    if "profile" not in (assignment.access_scope or []):
        raise HTTPException(status_code=403, detail={"code": "patient_profile_scope_not_granted"})
    scopes = assignment.access_scope
    patient = db.scalar(select(Patient).where(
        Patient.id == patient_id, Patient.hospital_id == hospital_id,
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    result = {
        "patient": {
            "id": patient.id, "medical_record_number": patient.medical_record_number,
            "given_name": patient.given_name, "middle_name": patient.middle_name,
            "family_name": patient.family_name, "date_of_birth": patient.date_of_birth,
            "administrative_sex": patient.administrative_sex, "phone_number": patient.phone_number,
        },
        "encounters": [], "lab_results": [], "medications": [],
    }
    if "encounters" in scopes:
        encounters = db.scalars(select(Encounter).where(
            Encounter.hospital_id == hospital_id, Encounter.patient_id == patient_id,
        ).order_by(Encounter.started_at.desc()).limit(50)).all()
        result["encounters"] = [{
            "id": row.id, "encounter_type": row.encounter_type, "status": row.status,
            "chief_complaint": row.chief_complaint, "started_at": row.started_at,
            "ended_at": row.ended_at,
        } for row in encounters]
    if "lab_results" in scopes:
        rows = db.execute(select(LaboratoryResult, LaboratorySpecimen).join(
            LaboratorySpecimen,
            and_(LaboratorySpecimen.hospital_id == LaboratoryResult.hospital_id,
                 LaboratorySpecimen.id == LaboratoryResult.specimen_id),
        ).join(
            LaboratoryOrder,
            and_(LaboratoryOrder.hospital_id == LaboratorySpecimen.hospital_id,
                 LaboratoryOrder.id == LaboratorySpecimen.order_id),
        ).where(
            LaboratoryResult.hospital_id == hospital_id,
            LaboratoryOrder.patient_id == patient_id,
            LaboratoryResult.status == "final",
        ).order_by(LaboratoryResult.entered_at.desc()).limit(100)).all()
        result["lab_results"] = [{
            "id": item.id, "accession_number": specimen.accession_number,
            "specimen_type": specimen.specimen_type, "value_text": item.value_text,
            "value_numeric": item.value_numeric, "unit": item.unit,
            "abnormality": item.abnormality, "critical_flag": item.critical_flag,
            "interpretation_note": item.interpretation_note, "entered_at": item.entered_at,
        } for item, specimen in rows]
    if "medications" in scopes:
        rows = db.execute(select(MedicationOrder, MedicationDefinition).join(
            MedicationDefinition,
            and_(MedicationDefinition.hospital_id == MedicationOrder.hospital_id,
                 MedicationDefinition.id == MedicationOrder.medication_definition_id),
        ).where(
            MedicationOrder.hospital_id == hospital_id,
            MedicationOrder.patient_id == patient_id,
        ).order_by(MedicationOrder.ordered_at.desc()).limit(100)).all()
        result["medications"] = [{
            "id": order.id, "medication_name": definition.generic_name,
            "strength": definition.strength_label, "dose_text": order.dose_text,
            "route": order.route, "frequency_text": order.frequency_text,
            "status": order.status, "ordered_at": order.ordered_at,
        } for order, definition in rows]
    _event(db, hospital_id, user.id, "patient_overview_viewed", "patient", patient.id, {"assignment_id": str(assignment.id) if assignment else None})
    _audit(db, hospital_id, user.id, "staff_portal.patient_overview_viewed", "patient", patient.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result


@router.get("/patients/{patient_id}/care-team", response_model=list[CareTeamAssignmentRead])
def get_patient_care_team(patient_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    if role not in _CLINICAL_ADMIN_ROLES:
        assignment = _care_assignment(db, user.id, hospital_id, patient_id)
        if "profile" not in (assignment.access_scope or []):
            raise HTTPException(status_code=403, detail={"code": "patient_profile_scope_not_granted"})
    now = datetime.now(timezone.utc)
    return db.scalars(select(PatientCareTeamAssignment).where(
        PatientCareTeamAssignment.hospital_id == hospital_id,
        PatientCareTeamAssignment.patient_id == patient_id,
        PatientCareTeamAssignment.status == "active",
        PatientCareTeamAssignment.starts_at <= now,
        or_(PatientCareTeamAssignment.ends_at.is_(None), PatientCareTeamAssignment.ends_at > now),
    ).order_by(PatientCareTeamAssignment.starts_at.desc())).all()


@router.post("/care-team/{assignment_id}/end", response_model=CareTeamAssignmentRead)
def end_patient_care_team(assignment_id: UUID, payload: CareTeamAssignmentEnd, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_role(db, user.id, hospital_id, _CLINICAL_ROLES | _CLINICAL_ADMIN_ROLES | {"department_head", "nurse_manager"})
    assignment = db.scalar(select(PatientCareTeamAssignment).where(
        PatientCareTeamAssignment.id == assignment_id,
        PatientCareTeamAssignment.hospital_id == hospital_id,
    ).with_for_update())
    if assignment is None or assignment.status != "active":
        raise HTTPException(status_code=404, detail={"code": "active_care_team_assignment_not_found"})
    manager_of_assignment = False
    if role == "department_head":
        employee = db.scalar(select(EmployeeProfile).where(
            EmployeeProfile.hospital_id == hospital_id, EmployeeProfile.user_id == user.id,
            EmployeeProfile.employment_status == "active",
        ))
        manager_of_assignment = employee is not None and assignment.department_id is not None and employee.department_id == assignment.department_id
    if role not in _CLINICAL_ADMIN_ROLES and not manager_of_assignment and assignment.staff_user_id != user.id and assignment.assigned_by_user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "care_team_assignment_management_denied"})
    if payload.status == "revoked" and assignment.staff_user_id == user.id and role not in _CLINICAL_ADMIN_ROLES and not manager_of_assignment and assignment.assigned_by_user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "only_assigner_or_manager_can_revoke_care_team_assignment"})
    assignment.status = payload.status
    assignment.ended_by_user_id = user.id
    assignment.ended_at = datetime.now(timezone.utc)
    assignment.end_reason = payload.reason
    _event(db, hospital_id, user.id, "care_team_ended", "patient_care_team_assignment", assignment.id, {"status": payload.status})
    _audit(db, hospital_id, user.id, "staff_portal.care_team_ended", "patient_care_team_assignment", assignment.id, {"status": payload.status})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(assignment)
    return assignment


@router.post("/tasks", response_model=StaffTaskRead, status_code=status.HTTP_201_CREATED)
def create_staff_task(payload: StaffTaskCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_role(db, user.id, hospital_id, _CLINICAL_ROLES | _CLINICAL_ADMIN_ROLES | {"department_head", "nurse_manager"})
    if role not in _CLINICAL_ADMIN_ROLES:
        _employee_profile(db, hospital_id, user.id)
        _verified_clinical_profile(db, hospital_id, user.id)
    if payload.due_at is not None and payload.due_at.tzinfo is None:
        raise HTTPException(status_code=422, detail={"code": "task_due_at_must_be_timezone_aware"})
    assigned_employee = _employee_profile(db, hospital_id, payload.assigned_to_user_id)
    if payload.patient_id is not None:
        patient = db.scalar(select(Patient.id).where(
            Patient.id == payload.patient_id, Patient.hospital_id == hospital_id,
        ))
        if patient is None:
            raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
        assignment = _care_assignment(db, payload.assigned_to_user_id, hospital_id, payload.patient_id)
        required_scope = {
            "review_lab_result": "lab_results",
            "medication_review": "medications",
            "sign_note": "encounters",
            "discharge_planning": "encounters",
            "follow_up": "encounters",
            "referral": "encounters",
            "care_coordination": "encounters",
        }.get(payload.task_type)
        if required_scope and required_scope not in (assignment.access_scope or []):
            raise HTTPException(status_code=403, detail={"code": "task_requires_patient_access_scope"})
    if payload.encounter_id is not None:
        if payload.patient_id is None:
            raise HTTPException(status_code=422, detail={"code": "encounter_task_requires_patient"})
        encounter = db.scalar(select(Encounter.id).where(
            Encounter.id == payload.encounter_id, Encounter.hospital_id == hospital_id,
            Encounter.patient_id == payload.patient_id,
        ))
        if encounter is None:
            raise HTTPException(status_code=404, detail={"code": "encounter_not_found"})
    if payload.department_id is not None:
        department = db.scalar(select(Department.id).where(
            Department.id == payload.department_id, Department.hospital_id == hospital_id,
            Department.status == "active",
        ))
        if department is None:
            raise HTTPException(status_code=404, detail={"code": "active_department_not_found"})
        if assigned_employee.department_id is not None and assigned_employee.department_id != department.id:
            raise HTTPException(status_code=422, detail={"code": "task_department_mismatch"})
    task = StaffWorkQueueTask(hospital_id=hospital_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(task)
    try:
        db.flush()
        _event(db, hospital_id, user.id, "task_created", "staff_work_queue_task", task.id)
        _audit(db, hospital_id, user.id, "staff_portal.task_created", "staff_work_queue_task", task.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "staff_task_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(task)
    return task


@router.get("/tasks", response_model=list[StaffTaskRead])
def list_staff_tasks(status_filter: str | None = Query(default=None, alias="status"), context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_role(db, user.id, hospital_id, _CLINICAL_ROLES | _CLINICAL_ADMIN_ROLES | {"department_head", "nurse_manager"})
    if role not in _CLINICAL_ADMIN_ROLES:
        _employee_profile(db, hospital_id, user.id)
        _verified_clinical_profile(db, hospital_id, user.id)
    query = select(StaffWorkQueueTask).where(
        StaffWorkQueueTask.hospital_id == hospital_id,
        StaffWorkQueueTask.assigned_to_user_id == user.id,
    )
    if status_filter is not None:
        if status_filter not in {"open", "in_progress", "completed", "cancelled"}:
            raise HTTPException(status_code=422, detail={"code": "invalid_task_status_filter"})
        query = query.where(StaffWorkQueueTask.status == status_filter)
    return db.scalars(query.order_by(
        StaffWorkQueueTask.priority.desc(), StaffWorkQueueTask.due_at.asc().nulls_last(),
    ).limit(300)).all()


@router.patch("/tasks/{task_id}", response_model=StaffTaskRead)
def update_staff_task(task_id: UUID, payload: StaffTaskUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    if role not in _CLINICAL_ADMIN_ROLES:
        _employee_profile(db, hospital_id, user.id)
        _verified_clinical_profile(db, hospital_id, user.id)
    task = db.scalar(select(StaffWorkQueueTask).where(
        StaffWorkQueueTask.id == task_id, StaffWorkQueueTask.hospital_id == hospital_id,
    ).with_for_update())
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "staff_task_not_found"})
    if task.assigned_to_user_id != user.id and role not in _CLINICAL_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={"code": "task_assignee_only"})
    if task.status in ("completed", "cancelled"):
        raise HTTPException(status_code=409, detail={"code": "terminal_task_status"})
    task.status = payload.status
    if payload.status == "completed":
        if not payload.completion_note or len(payload.completion_note.strip()) < 5:
            raise HTTPException(status_code=422, detail={"code": "task_completion_note_required"})
        task.completed_by_user_id = user.id
        task.completed_at = datetime.now(timezone.utc)
        task.completion_note = payload.completion_note
    else:
        task.completed_by_user_id = None
        task.completed_at = None
        task.completion_note = None
    _event(db, hospital_id, user.id, "task_status_changed", "staff_work_queue_task", task.id, {"status": payload.status})
    _audit(db, hospital_id, user.id, "staff_portal.task_status_changed", "staff_work_queue_task", task.id, {"status": payload.status})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(task)
    return task


@router.get("/dashboard")
def get_staff_portal_dashboard(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_role(db, user.id, hospital_id, _CLINICAL_ROLES | _CLINICAL_ADMIN_ROLES | {"department_head", "nurse_manager"})
    if role not in _CLINICAL_ADMIN_ROLES:
        _employee_profile(db, hospital_id, user.id)
        _verified_clinical_profile(db, hospital_id, user.id)
    now = datetime.now(timezone.utc)
    return {
        "tasks_open": db.scalar(select(func.count()).select_from(StaffWorkQueueTask).where(
            StaffWorkQueueTask.hospital_id == hospital_id,
            StaffWorkQueueTask.assigned_to_user_id == user.id,
            StaffWorkQueueTask.status.in_(["open", "in_progress"]),
        )) or 0,
        "patients_assigned": db.scalar(select(func.count()).select_from(PatientCareTeamAssignment).where(
            PatientCareTeamAssignment.hospital_id == hospital_id,
            PatientCareTeamAssignment.staff_user_id == user.id,
            PatientCareTeamAssignment.status == "active",
            or_(PatientCareTeamAssignment.ends_at.is_(None), PatientCareTeamAssignment.ends_at > now),
        )) or 0,
        "clinical_profile_status": (db.scalar(select(ClinicalStaffProfile.status).where(
            ClinicalStaffProfile.hospital_id == hospital_id,
            ClinicalStaffProfile.user_id == user.id,
        )) or "not_submitted"),
    }
