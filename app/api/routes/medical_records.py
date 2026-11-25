from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import Encounter, HospitalMembership, Patient, PatientConsent, Role, User
from app.models.hr import EmployeeProfile
from app.models.staff_portal import ClinicalStaffProfile, PatientCareTeamAssignment
from app.models.patient_records import (
    PatientRecordDocument, PatientRecordReleaseRequest,
    PatientRecordAmendmentRequest, PatientRecordEvent,
)
from app.schemas.patient_records import (
    RecordDocumentCreate, RecordDocumentDecision, RecordDocumentRead,
    RecordReleaseCreate, RecordReleaseDecision, RecordReleaseComplete, RecordReleaseRead,
    RecordAmendmentCreate, RecordAmendmentDecision, RecordAmendmentFulfil, RecordAmendmentRead,
)
from app.services.patient_authorization import has_active_patient_authorization

router = APIRouter(prefix="/medical-records", tags=["medical records and health information"])
_HIM_ROLES = {"medical_records_officer", "health_information_manager", "medical_records_manager"}
_RECORD_SCOPE = {
    "lab_report": "lab_results",
    "prescription": "medications",
    "clinical_note": "encounters",
    "discharge_summary": "encounters",
    "imaging_report": "encounters",
    "referral": "encounters",
    "consent": "encounters",
    "identity_document": "profile",
    "administrative": "profile",
    "external_record": "encounters",
    "other": "encounters",
}


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


def _require_him(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    if _role(db, user_id, hospital_id) not in _HIM_ROLES:
        raise HTTPException(status_code=403, detail={"code": "medical_records_officer_role_required"})


def _patient(db: Session, hospital_id: UUID, patient_id: UUID) -> Patient:
    patient = db.scalar(select(Patient).where(
        Patient.hospital_id == hospital_id, Patient.id == patient_id,
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    return patient


def _require_patient_record_access(db: Session, user_id: UUID, hospital_id: UUID, patient_id: UUID, record_type: str | None = None) -> set[str] | None:
    if _role(db, user_id, hospital_id) in _HIM_ROLES:
        return None
    now = datetime.now(timezone.utc)
    membership = db.scalar(select(HospitalMembership.id).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ).limit(1))
    employee = db.scalar(select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id,
        EmployeeProfile.user_id == user_id,
        EmployeeProfile.employment_status == "active",
    ))
    profile = db.scalar(select(ClinicalStaffProfile).where(
        ClinicalStaffProfile.hospital_id == hospital_id,
        ClinicalStaffProfile.user_id == user_id,
        ClinicalStaffProfile.status == "verified",
        or_(ClinicalStaffProfile.license_expires_at.is_(None), ClinicalStaffProfile.license_expires_at > now),
    ))
    user = db.get(User, user_id)
    assignment = db.scalar(select(PatientCareTeamAssignment).where(
        PatientCareTeamAssignment.hospital_id == hospital_id,
        PatientCareTeamAssignment.patient_id == patient_id,
        PatientCareTeamAssignment.staff_user_id == user_id,
        PatientCareTeamAssignment.status == "active",
        PatientCareTeamAssignment.starts_at <= now,
        or_(PatientCareTeamAssignment.ends_at.is_(None), PatientCareTeamAssignment.ends_at > now),
    ))
    scopes = set(assignment.access_scope or []) if assignment is not None else set()
    required_scope = _RECORD_SCOPE.get(record_type, "encounters") if record_type is not None else None
    if (
        membership is None or employee is None or profile is None or user is None
        or not user.is_active or assignment is None
        or (required_scope is not None and required_scope not in scopes)
    ):
        raise HTTPException(status_code=403, detail={"code": "active_scoped_care_team_access_required"})
    return scopes


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _event(db: Session, hospital_id: UUID, patient_id: UUID, user_id: UUID, event_type: str, resource_type: str, resource_id: UUID, metadata=None) -> None:
    db.add(PatientRecordEvent(
        hospital_id=hospital_id, patient_id=patient_id, actor_user_id=user_id,
        event_type=event_type, resource_type=resource_type, resource_id=resource_id,
        event_metadata=metadata or {},
    ))


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource_type: str, resource_id: UUID, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource_type, resource_id=str(resource_id), metadata=metadata or {},
    )


_CATEGORY_SCOPE = {
    "demographics": "profile", "contact_details": "profile",
    "clinical_records": "encounters", "lab_results": "lab_results",
    "imaging": "encounters", "medications": "medications",
    "billing": "billing", "insurance": "insurance", "other": "other",
}
_RELEASE_USE = {
    "record_sharing": "record_sharing", "care_coordination": "care_coordination",
    "referral": "referral", "patient_portal": "patient_portal",
    "insurance_claim": "insurance_claim", "legal_requirement": "record_sharing",
    "other": "other_lawful_use",
}


def _active_release_consent(db: Session, hospital_id: UUID, patient_id: UUID, consent_id: UUID, categories: list[str], release_purpose: str):
    now = datetime.now(timezone.utc)
    consent = db.scalar(select(PatientConsent).where(
        PatientConsent.hospital_id == hospital_id,
        PatientConsent.patient_id == patient_id,
        PatientConsent.id == consent_id,
    ))
    if (
        consent is None or consent.purpose != "record_sharing" or consent.status != "granted"
        or consent.basis_code is None or consent.granted_at is None or consent.granted_at > now
        or consent.withdrawn_at is not None
        or (consent.expires_at is not None and consent.expires_at <= now)
    ):
        raise HTTPException(status_code=403, detail={"code": "active_record_sharing_authorization_required"})
    if release_purpose == "legal_requirement" and consent.basis_code != "legal_requirement":
        raise HTTPException(status_code=403, detail={"code": "legal_requirement_basis_must_be_declared"})
    scope = consent.scope if isinstance(consent.scope, dict) else {}
    allowed_categories = scope.get("data_categories", [])
    permitted_uses = scope.get("permitted_uses", [])
    if (
        not isinstance(allowed_categories, list) or not isinstance(permitted_uses, list)
        or not all(isinstance(value, str) for value in allowed_categories + permitted_uses)
        or not set(categories).issubset(set(allowed_categories))
        or "record_sharing" not in permitted_uses
        or _RELEASE_USE.get(release_purpose, "other_lawful_use") not in permitted_uses
        or not has_active_patient_authorization(
            db, hospital_id=hospital_id, patient_id=patient_id,
            purpose="record_sharing", data_categories=set(categories),
            permitted_use="record_sharing", now=now,
        )
        or not has_active_patient_authorization(
            db, hospital_id=hospital_id, patient_id=patient_id,
            purpose="record_sharing", data_categories=set(categories),
            permitted_use=_RELEASE_USE.get(release_purpose, "other_lawful_use"), now=now,
        )
    ):
        raise HTTPException(status_code=403, detail={"code": "record_sharing_scope_not_authorized"})
    return consent


@router.post("/documents", response_model=RecordDocumentRead, status_code=status.HTTP_201_CREATED)
def register_record_document(payload: RecordDocumentCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_him(db, user.id, hospital_id)
    _patient(db, hospital_id, payload.patient_id)
    if payload.encounter_id is not None:
        encounter = db.scalar(select(Encounter).where(
            Encounter.hospital_id == hospital_id,
            Encounter.id == payload.encounter_id,
            Encounter.patient_id == payload.patient_id,
        ))
        if encounter is None:
            raise HTTPException(status_code=404, detail={"code": "patient_encounter_not_found"})
    if payload.supersedes_document_id is not None:
        previous = db.scalar(select(PatientRecordDocument).where(
            PatientRecordDocument.hospital_id == hospital_id,
            PatientRecordDocument.patient_id == payload.patient_id,
            PatientRecordDocument.id == payload.supersedes_document_id,
        ).with_for_update())
        if (
            previous is None or previous.status != "verified"
            or previous.source_module != payload.source_module
            or previous.source_record_id != payload.source_record_id
            or previous.record_type != payload.record_type
            or previous.encounter_id != payload.encounter_id
            or payload.version_number != previous.version_number + 1
        ):
            raise HTTPException(status_code=409, detail={"code": "valid_verified_previous_document_version_required"})
    document = PatientRecordDocument(
        hospital_id=hospital_id, created_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(document)
    try:
        db.flush()
        _event(db, hospital_id, payload.patient_id, user.id, "document_registered", "patient_record_document", document.id, {"record_type": document.record_type, "source_module": document.source_module})
        _audit(db, hospital_id, user.id, "medical_records.document_registered", "patient_record_document", document.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "record_document_reference_or_version_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(document)
    return document


@router.get("/patients/{patient_id}/documents", response_model=list[RecordDocumentRead])
def list_patient_record_documents(patient_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _patient(db, hospital_id, patient_id)
    scopes = _require_patient_record_access(db, user.id, hospital_id, patient_id)
    is_him = scopes is None
    query = select(PatientRecordDocument).where(
        PatientRecordDocument.hospital_id == hospital_id,
        PatientRecordDocument.patient_id == patient_id,
    )
    if not is_him:
        query = query.where(PatientRecordDocument.status == "verified")
    rows = db.scalars(query.order_by(PatientRecordDocument.document_date.desc()).limit(500)).all()
    if not is_him:
        rows = [row for row in rows if _RECORD_SCOPE.get(row.record_type, "encounters") in scopes]
    _audit(db, hospital_id, user.id, "medical_records.patient_documents_viewed", "patient", patient_id, {"result_count": len(rows)})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return rows


@router.get("/documents/{document_id}", response_model=RecordDocumentRead)
def get_record_document(document_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    document = db.scalar(select(PatientRecordDocument).where(
        PatientRecordDocument.hospital_id == hospital_id,
        PatientRecordDocument.id == document_id,
    ))
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "record_document_not_found"})
    _require_patient_record_access(db, user.id, hospital_id, document.patient_id, document.record_type)
    if document.status != "verified" and _role(db, user.id, hospital_id) not in _HIM_ROLES:
        raise HTTPException(status_code=404, detail={"code": "record_document_not_found"})
    _audit(db, hospital_id, user.id, "medical_records.document_viewed", "patient_record_document", document.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return document


@router.post("/documents/{document_id}/decision", response_model=RecordDocumentRead)
def decide_record_document(document_id: UUID, payload: RecordDocumentDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_him(db, user.id, hospital_id)
    document = db.scalar(select(PatientRecordDocument).where(
        PatientRecordDocument.hospital_id == hospital_id,
        PatientRecordDocument.id == document_id,
    ).with_for_update())
    if document is None or document.status != "pending_review":
        raise HTTPException(status_code=404, detail={"code": "pending_record_document_not_found"})
    if document.created_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_document_verification_required"})
    now = datetime.now(timezone.utc)
    document.verified_by_user_id = user.id
    document.verified_at = now
    if payload.decision == "verify":
        if document.supersedes_document_id is not None:
            previous = db.scalar(select(PatientRecordDocument).where(
                PatientRecordDocument.hospital_id == hospital_id,
                PatientRecordDocument.patient_id == document.patient_id,
                PatientRecordDocument.id == document.supersedes_document_id,
            ).with_for_update())
            if previous is None or previous.status != "verified":
                raise HTTPException(status_code=409, detail={"code": "previous_verified_document_required"})
            previous.status = "superseded"
            _event(db, hospital_id, document.patient_id, user.id, "document_superseded", "patient_record_document", previous.id, {"superseded_by": str(document.id)})
        document.status = "verified"
        event_type = "document_verified"
    else:
        document.status = "rejected"
        document.rejection_reason = payload.reason
        event_type = "document_rejected"
    _event(db, hospital_id, document.patient_id, user.id, event_type, "patient_record_document", document.id)
    _audit(db, hospital_id, user.id, "medical_records.document_decided", "patient_record_document", document.id, {"decision": payload.decision})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(document)
    return document


@router.post("/release-requests", response_model=RecordReleaseRead, status_code=status.HTTP_201_CREATED)
def create_record_release_request(payload: RecordReleaseCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _patient(db, hospital_id, payload.patient_id)
    if payload.requester_type in {"patient", "legal_representative"}:
        raise HTTPException(status_code=403, detail={"code": "patient_proxy_identity_workflow_not_connected"})
    is_him = _role(db, user.id, hospital_id) in _HIM_ROLES
    if payload.requester_type != "treating_provider" and not is_him:
        raise HTTPException(status_code=403, detail={"code": "external_requester_must_be_registered_by_records_officer"})
    if not is_him:
        scopes = _require_patient_record_access(db, user.id, hospital_id, payload.patient_id)
        if any(_CATEGORY_SCOPE.get(category, "encounters") not in scopes for category in payload.data_categories):
            raise HTTPException(status_code=403, detail={"code": "release_categories_exceed_staff_access_scope"})
    _active_release_consent(db, hospital_id, payload.patient_id, payload.consent_id, payload.data_categories, payload.purpose)
    request = PatientRecordReleaseRequest(
        hospital_id=hospital_id, requester_user_id=user.id,
        status="pending", **payload.model_dump(),
    )
    db.add(request)
    db.flush()
    _event(db, hospital_id, payload.patient_id, user.id, "release_requested", "patient_record_release_request", request.id, {"purpose": payload.purpose, "data_categories": payload.data_categories})
    _audit(db, hospital_id, user.id, "medical_records.release_requested", "patient_record_release_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.get("/release-requests", response_model=list[RecordReleaseRead])
def list_record_release_requests(patient_id: UUID | None = None, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    query = select(PatientRecordReleaseRequest).where(PatientRecordReleaseRequest.hospital_id == hospital_id)
    if _role(db, user.id, hospital_id) not in _HIM_ROLES:
        query = query.where(PatientRecordReleaseRequest.requester_user_id == user.id)
    if patient_id is not None:
        query = query.where(PatientRecordReleaseRequest.patient_id == patient_id)
    return db.scalars(query.order_by(PatientRecordReleaseRequest.created_at.desc()).limit(300)).all()


@router.post("/release-requests/{request_id}/cancel", response_model=RecordReleaseRead)
def cancel_record_release_request(request_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    request = db.scalar(select(PatientRecordReleaseRequest).where(
        PatientRecordReleaseRequest.hospital_id == hospital_id,
        PatientRecordReleaseRequest.id == request_id,
    ).with_for_update())
    if request is None or request.requester_user_id != user.id or request.status != "pending":
        raise HTTPException(status_code=404, detail={"code": "cancellable_own_record_release_not_found"})
    request.status = "cancelled"
    _event(db, hospital_id, request.patient_id, user.id, "release_cancelled", "patient_record_release_request", request.id)
    _audit(db, hospital_id, user.id, "medical_records.release_cancelled", "patient_record_release_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.post("/release-requests/{request_id}/decision", response_model=RecordReleaseRead)
def decide_record_release_request(request_id: UUID, payload: RecordReleaseDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_him(db, user.id, hospital_id)
    request = db.scalar(select(PatientRecordReleaseRequest).where(
        PatientRecordReleaseRequest.hospital_id == hospital_id,
        PatientRecordReleaseRequest.id == request_id,
    ).with_for_update())
    if request is None or request.status != "pending":
        raise HTTPException(status_code=404, detail={"code": "pending_record_release_not_found"})
    if request.requester_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_record_release_review_required"})
    _active_release_consent(db, hospital_id, request.patient_id, request.consent_id, request.data_categories, request.purpose)
    request.reviewed_by_user_id = user.id
    request.reviewed_at = datetime.now(timezone.utc)
    if payload.decision == "approve":
        request.status = "approved"
        event_type = "release_approved"
    else:
        request.status = "rejected"
        request.decision_reason = payload.reason
        event_type = "release_rejected"
    _event(db, hospital_id, request.patient_id, user.id, event_type, "patient_record_release_request", request.id)
    _audit(db, hospital_id, user.id, "medical_records.release_decided", "patient_record_release_request", request.id, {"decision": payload.decision})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.post("/release-requests/{request_id}/complete", response_model=RecordReleaseRead)
def complete_record_release(request_id: UUID, payload: RecordReleaseComplete, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_him(db, user.id, hospital_id)
    request = db.scalar(select(PatientRecordReleaseRequest).where(
        PatientRecordReleaseRequest.hospital_id == hospital_id,
        PatientRecordReleaseRequest.id == request_id,
    ).with_for_update())
    if request is None or request.status != "approved":
        raise HTTPException(status_code=404, detail={"code": "approved_record_release_not_found"})
    if request.reviewed_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_record_release_completion_required"})
    _active_release_consent(db, hospital_id, request.patient_id, request.consent_id, request.data_categories)
    request.status = "released"
    request.released_by_user_id = user.id
    request.released_at = datetime.now(timezone.utc)
    request.release_vault_reference = payload.release_vault_reference
    _event(db, hospital_id, request.patient_id, user.id, "records_released", "patient_record_release_request", request.id, {"data_categories": request.data_categories})
    _audit(db, hospital_id, user.id, "medical_records.release_completed", "patient_record_release_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.post("/amendment-requests", response_model=RecordAmendmentRead, status_code=status.HTTP_201_CREATED)
def create_record_amendment_request(payload: RecordAmendmentCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _patient(db, hospital_id, payload.patient_id)
    if _role(db, user.id, hospital_id) not in _HIM_ROLES:
        scopes = _require_patient_record_access(db, user.id, hospital_id, payload.patient_id)
        required_scope = {"demographic": "profile", "identity": "profile", "clinical_content": "encounters", "metadata": "encounters"}[payload.amendment_type]
        if required_scope not in scopes:
            raise HTTPException(status_code=403, detail={"code": "amendment_scope_not_authorized"})
    if payload.document_id is not None:
        document = db.scalar(select(PatientRecordDocument).where(
            PatientRecordDocument.hospital_id == hospital_id,
            PatientRecordDocument.patient_id == payload.patient_id,
            PatientRecordDocument.id == payload.document_id,
            PatientRecordDocument.status == "verified",
        ))
        if document is None:
            raise HTTPException(status_code=404, detail={"code": "verified_patient_record_document_not_found"})
        if _role(db, user.id, hospital_id) not in _HIM_ROLES:
            _require_patient_record_access(db, user.id, hospital_id, payload.patient_id, document.record_type)
    request = PatientRecordAmendmentRequest(
        hospital_id=hospital_id, requested_by_user_id=user.id,
        status="pending", **payload.model_dump(),
    )
    db.add(request)
    db.flush()
    _event(db, hospital_id, payload.patient_id, user.id, "amendment_requested", "patient_record_amendment_request", request.id)
    _audit(db, hospital_id, user.id, "medical_records.amendment_requested", "patient_record_amendment_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.get("/amendment-requests", response_model=list[RecordAmendmentRead])
def list_record_amendment_requests(patient_id: UUID | None = None, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    query = select(PatientRecordAmendmentRequest).where(PatientRecordAmendmentRequest.hospital_id == hospital_id)
    if _role(db, user.id, hospital_id) not in _HIM_ROLES:
        query = query.where(PatientRecordAmendmentRequest.requested_by_user_id == user.id)
    if patient_id is not None:
        query = query.where(PatientRecordAmendmentRequest.patient_id == patient_id)
    return db.scalars(query.order_by(PatientRecordAmendmentRequest.created_at.desc()).limit(300)).all()


@router.post("/amendment-requests/{request_id}/cancel", response_model=RecordAmendmentRead)
def cancel_record_amendment_request(request_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    request = db.scalar(select(PatientRecordAmendmentRequest).where(
        PatientRecordAmendmentRequest.hospital_id == hospital_id,
        PatientRecordAmendmentRequest.id == request_id,
    ).with_for_update())
    if request is None or request.requested_by_user_id != user.id or request.status != "pending":
        raise HTTPException(status_code=404, detail={"code": "cancellable_own_record_amendment_not_found"})
    request.status = "cancelled"
    _event(db, hospital_id, request.patient_id, user.id, "amendment_cancelled", "patient_record_amendment_request", request.id)
    _audit(db, hospital_id, user.id, "medical_records.amendment_cancelled", "patient_record_amendment_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.post("/amendment-requests/{request_id}/decision", response_model=RecordAmendmentRead)
def decide_record_amendment_request(request_id: UUID, payload: RecordAmendmentDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_him(db, user.id, hospital_id)
    request = db.scalar(select(PatientRecordAmendmentRequest).where(
        PatientRecordAmendmentRequest.hospital_id == hospital_id,
        PatientRecordAmendmentRequest.id == request_id,
    ).with_for_update())
    if request is None or request.status != "pending":
        raise HTTPException(status_code=404, detail={"code": "pending_record_amendment_not_found"})
    if request.requested_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_record_amendment_review_required"})
    request.reviewed_by_user_id = user.id
    request.reviewed_at = datetime.now(timezone.utc)
    if payload.decision == "approve":
        request.status = "approved"
        event_type = "amendment_approved"
    else:
        request.status = "rejected"
        request.decision_reason = payload.reason
        event_type = "amendment_rejected"
    _event(db, hospital_id, request.patient_id, user.id, event_type, "patient_record_amendment_request", request.id)
    _audit(db, hospital_id, user.id, "medical_records.amendment_decided", "patient_record_amendment_request", request.id, {"decision": payload.decision})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.post("/amendment-requests/{request_id}/fulfil", response_model=RecordAmendmentRead)
def fulfil_record_amendment_request(request_id: UUID, payload: RecordAmendmentFulfil, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_him(db, user.id, hospital_id)
    request = db.scalar(select(PatientRecordAmendmentRequest).where(
        PatientRecordAmendmentRequest.hospital_id == hospital_id,
        PatientRecordAmendmentRequest.id == request_id,
    ).with_for_update())
    if request is None or request.status != "approved":
        raise HTTPException(status_code=404, detail={"code": "approved_record_amendment_not_found"})
    if request.reviewed_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_record_amendment_fulfilment_required"})
    request.status = "fulfilled"
    request.fulfilled_by_user_id = user.id
    request.fulfilled_at = datetime.now(timezone.utc)
    request.amendment_vault_reference = payload.amendment_vault_reference
    _event(db, hospital_id, request.patient_id, user.id, "amendment_fulfilled", "patient_record_amendment_request", request.id)
    _audit(db, hospital_id, user.id, "medical_records.amendment_fulfilled", "patient_record_amendment_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request
