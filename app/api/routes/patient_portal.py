from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context, get_current_patient_context
from app.db.session import get_db
from app.models import (
    Encounter, HospitalMembership, Patient, PatientConsent, Role, User,
)
from app.models.patient_portal import PatientPortalLink, PatientPortalAccessEvent
from app.models.laboratory import (
    LaboratoryOrder, LaboratorySpecimen, LaboratoryResult, LaboratoryCriticalAcknowledgement,
)
from app.models.pharmacy import MedicationDefinition, MedicationOrder
from app.models.billing import Invoice
from app.schemas.patient_portal import (
    PatientPortalLinkCreate, PatientPortalLinkVerification, PatientPortalLinkRevocation,
    PatientPortalLinkRead, PatientPortalPatientRead, PatientPortalEncounterRead,
    PatientPortalLabResultRead, PatientPortalMedicationRead, PatientPortalInvoiceRead,
    PatientPortalConsentRead,
)

router = APIRouter(prefix="/patient-portal", tags=["patient portal"])
_PORTAL_STAFF = {"medical_records_officer", "hospital_admin", "hospital_director", "patient_portal_admin"}
_ALLOWED_SCOPES = {"profile", "encounters", "lab_results", "medications", "invoices", "consents"}
_SELF_VERIFICATION = {"in_person", "identity_document", "verified_email", "verified_phone"}
_PROXY_VERIFICATION = {"guardian_document", "court_order"}


def _require_portal_staff(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    membership = db.scalar(select(HospitalMembership).join(
        Role, Role.id == HospitalMembership.role_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    role_name = role.name.strip().casefold().replace(" ", "_") if role else ""
    if role_name not in _PORTAL_STAFF:
        raise HTTPException(status_code=403, detail={"code": "patient_portal_staff_role_required"})


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    from sqlalchemy import text
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource_type: str, resource_id: UUID | None, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource_type, resource_id=str(resource_id) if resource_id else None,
        metadata=metadata or {},
    )


def _active_link(db: Session, user_id: UUID, hospital_id: UUID, patient_id: UUID):
    now = datetime.now(timezone.utc)
    link = db.scalar(select(PatientPortalLink).where(
        PatientPortalLink.hospital_id == hospital_id,
        PatientPortalLink.portal_user_id == user_id,
        PatientPortalLink.patient_id == patient_id,
        PatientPortalLink.status == "active",
        or_(PatientPortalLink.expires_at.is_(None), PatientPortalLink.expires_at > now),
    ))
    if link is None:
        raise HTTPException(status_code=404, detail={"code": "active_patient_portal_link_not_found"})
    return link


def _require_scope(link: PatientPortalLink, scope: str) -> None:
    if scope not in (link.access_scope or []):
        raise HTTPException(status_code=403, detail={"code": "patient_portal_scope_not_granted"})


def _record_access(db: Session, user_id: UUID, hospital_id: UUID, link: PatientPortalLink, action: str, count: int) -> None:
    db.add(PatientPortalAccessEvent(
        hospital_id=hospital_id, portal_link_id=link.id, patient_id=link.patient_id,
        portal_user_id=user_id, action=action, resource_count=count,
    ))
    _audit(db, hospital_id, user_id, "patient_portal."+action, "patient_portal_link", link.id, {"resource_count": count})


@router.post("/links", response_model=PatientPortalLinkRead, status_code=status.HTTP_201_CREATED)
def create_patient_portal_link(payload: PatientPortalLinkCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_portal_staff(db, user.id, hospital_id)
    if not payload.access_scope or len(set(payload.access_scope)) != len(payload.access_scope) or not set(payload.access_scope).issubset(_ALLOWED_SCOPES):
        raise HTTPException(status_code=422, detail={"code": "invalid_patient_portal_access_scope"})
    if payload.expires_at is not None and (payload.expires_at.tzinfo is None or payload.expires_at <= datetime.now(timezone.utc)):
        raise HTTPException(status_code=422, detail={"code": "portal_link_expiry_must_be_future_and_timezone_aware"})
    if payload.relationship_type == "self" and payload.authority_reference is not None:
        raise HTTPException(status_code=422, detail={"code": "self_link_must_not_use_proxy_authority"})
    if payload.relationship_type != "self":
        if not payload.authority_reference or payload.expires_at is None or payload.expires_at.tzinfo is None:
            raise HTTPException(status_code=422, detail={"code": "proxy_link_requires_authority_reference_and_timezone_expiry"})
        if payload.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail={"code": "proxy_link_expiry_must_be_future"})
    patient = db.scalar(select(Patient).where(
        Patient.id == payload.patient_id, Patient.hospital_id == hospital_id,
    ))
    portal_user = db.get(User, payload.portal_user_id)
    if patient is None or portal_user is None or not portal_user.is_active:
        raise HTTPException(status_code=404, detail={"code": "active_patient_and_portal_user_required"})
    link = PatientPortalLink(
        hospital_id=hospital_id, requested_by_user_id=user.id,
        status="pending", **payload.model_dump(),
    )
    db.add(link)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "patient_portal.link_requested", "patient_portal_link", link.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "patient_portal_link_already_exists"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(link)
    return link


@router.get("/links", response_model=list[PatientPortalLinkRead])
def list_patient_portal_links(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_portal_staff(db, user.id, hospital_id)
    return db.scalars(select(PatientPortalLink).where(
        PatientPortalLink.hospital_id == hospital_id,
    ).order_by(PatientPortalLink.created_at.desc()).limit(300)).all()


@router.post("/links/{link_id}/verify", response_model=PatientPortalLinkRead)
def verify_patient_portal_link(link_id: UUID, payload: PatientPortalLinkVerification, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_portal_staff(db, user.id, hospital_id)
    link = db.scalar(select(PatientPortalLink).where(
        PatientPortalLink.id == link_id, PatientPortalLink.hospital_id == hospital_id,
    ).with_for_update())
    if link is None or link.status != "pending":
        raise HTTPException(status_code=404, detail={"code": "pending_patient_portal_link_not_found"})
    if link.requested_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_patient_identity_verification_required"})
    if link.relationship_type == "self" and payload.verification_method not in _SELF_VERIFICATION:
        raise HTTPException(status_code=422, detail={"code": "self_link_requires_identity_verification"})
    if link.relationship_type == "legal_representative" and payload.verification_method != "court_order":
        raise HTTPException(status_code=422, detail={"code": "legal_representative_requires_court_order"})
    if link.relationship_type in ("parent_guardian", "caregiver") and payload.verification_method not in _PROXY_VERIFICATION:
        raise HTTPException(status_code=422, detail={"code": "proxy_link_requires_guardian_or_legal_document"})
    if link.expires_at is not None and link.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail={"code": "patient_portal_link_expired"})
    link.status = "active"
    link.verification_method = payload.verification_method
    link.evidence_reference = payload.evidence_reference
    link.verified_by_user_id = user.id
    link.verified_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "patient_portal.link_verified", "patient_portal_link", link.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(link)
    return link


@router.post("/links/{link_id}/revoke", response_model=PatientPortalLinkRead)
def revoke_patient_portal_link(link_id: UUID, payload: PatientPortalLinkRevocation, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_portal_staff(db, user.id, hospital_id)
    link = db.scalar(select(PatientPortalLink).where(
        PatientPortalLink.id == link_id, PatientPortalLink.hospital_id == hospital_id,
    ).with_for_update())
    if link is None or link.status == "revoked":
        raise HTTPException(status_code=404, detail={"code": "active_patient_portal_link_not_found"})
    link.status = "revoked"
    link.verified_by_user_id = None
    link.verified_at = None
    link.revoked_by_user_id = user.id
    link.revoked_at = datetime.now(timezone.utc)
    link.revocation_reason = payload.reason
    _audit(db, hospital_id, user.id, "patient_portal.link_revoked", "patient_portal_link", link.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(link)
    return link


@router.get("/patients", response_model=list[PatientPortalPatientRead])
def list_linked_patients(context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    now = datetime.now(timezone.utc)
    rows = db.execute(select(PatientPortalLink, Patient).join(
        Patient, and_(Patient.id == PatientPortalLink.patient_id, Patient.hospital_id == PatientPortalLink.hospital_id),
    ).where(
        PatientPortalLink.hospital_id == hospital_id,
        PatientPortalLink.portal_user_id == user.id,
        PatientPortalLink.status == "active",
        or_(PatientPortalLink.expires_at.is_(None), PatientPortalLink.expires_at > now),
    ).order_by(Patient.family_name, Patient.given_name)).all()
    result = []
    for link, patient in rows:
        if "profile" not in (link.access_scope or []):
            continue
        result.append({
            "patient_id": patient.id, "medical_record_number": patient.medical_record_number,
            "given_name": patient.given_name, "middle_name": patient.middle_name,
            "preferred_name": patient.preferred_name, "family_name": patient.family_name,
            "date_of_birth": patient.date_of_birth, "administrative_sex": patient.administrative_sex,
            "phone_number": patient.phone_number, "relationship_type": link.relationship_type,
            "access_scope": link.access_scope,
        })
        _record_access(db, user.id, hospital_id, link, "viewed_profile", 1)
    if result:
        db.commit()
        _restore_context(db, user.id, hospital_id)
    return result


@router.get("/patients/{patient_id}", response_model=PatientPortalPatientRead)
def get_linked_patient(patient_id: UUID, context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    link = _active_link(db, user.id, hospital_id, patient_id)
    _require_scope(link, "profile")
    patient = db.scalar(select(Patient).where(
        Patient.id == patient_id, Patient.hospital_id == hospital_id,
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    _record_access(db, user.id, hospital_id, link, "viewed_profile", 1)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return {
        "patient_id": patient.id, "medical_record_number": patient.medical_record_number,
        "given_name": patient.given_name, "middle_name": patient.middle_name,
        "preferred_name": patient.preferred_name, "family_name": patient.family_name,
        "date_of_birth": patient.date_of_birth, "administrative_sex": patient.administrative_sex,
        "phone_number": patient.phone_number, "relationship_type": link.relationship_type,
        "access_scope": link.access_scope,
    }


@router.get("/patients/{patient_id}/encounters", response_model=list[PatientPortalEncounterRead])
def list_patient_encounters(patient_id: UUID, context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    link = _active_link(db, user.id, hospital_id, patient_id)
    _require_scope(link, "encounters")
    rows = db.scalars(select(Encounter).where(
        Encounter.hospital_id == hospital_id, Encounter.patient_id == patient_id,
    ).order_by(Encounter.started_at.desc()).limit(200)).all()
    _record_access(db, user.id, hospital_id, link, "viewed_encounters", len(rows))
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return rows


@router.get("/patients/{patient_id}/lab-results", response_model=list[PatientPortalLabResultRead])
def list_patient_lab_results(patient_id: UUID, context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    link = _active_link(db, user.id, hospital_id, patient_id)
    _require_scope(link, "lab_results")
    critical_ack = select(LaboratoryCriticalAcknowledgement.id).where(
        LaboratoryCriticalAcknowledgement.hospital_id == hospital_id,
        LaboratoryCriticalAcknowledgement.result_id == LaboratoryResult.id,
    ).exists()
    rows = db.execute(select(
        LaboratoryResult, LaboratorySpecimen,
    ).join(
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
        or_(LaboratoryResult.critical_flag.is_(False), critical_ack),
    ).order_by(LaboratoryResult.entered_at.desc()).limit(300)).all()
    result = [{
        "id": item.id, "specimen_accession_number": specimen.accession_number,
        "specimen_type": specimen.specimen_type, "value_text": item.value_text,
        "value_numeric": item.value_numeric, "unit": item.unit,
        "abnormality": item.abnormality, "critical_flag": item.critical_flag,
        "interpretation_note": item.interpretation_note, "entered_at": item.entered_at,
    } for item, specimen in rows]
    _record_access(db, user.id, hospital_id, link, "viewed_lab_results", len(result))
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result


@router.get("/patients/{patient_id}/medications", response_model=list[PatientPortalMedicationRead])
def list_patient_medications(patient_id: UUID, context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    link = _active_link(db, user.id, hospital_id, patient_id)
    _require_scope(link, "medications")
    rows = db.execute(select(
        MedicationOrder, MedicationDefinition,
    ).join(
        MedicationDefinition,
        and_(MedicationDefinition.hospital_id == MedicationOrder.hospital_id,
             MedicationDefinition.id == MedicationOrder.medication_definition_id),
    ).where(
        MedicationOrder.hospital_id == hospital_id,
        MedicationOrder.patient_id == patient_id,
    ).order_by(MedicationOrder.ordered_at.desc()).limit(300)).all()
    result = [{
        "id": order.id,
        "medication_name": definition.generic_name,
        "strength": definition.strength_label,
        "dose_text": order.dose_text,
        "route": order.route,
        "frequency_text": order.frequency_text,
        "duration_days": order.duration_days,
        "quantity_prescribed": order.quantity_prescribed,
        "quantity_unit": order.quantity_unit,
        "instructions": order.instructions,
        "status": order.status,
        "ordered_at": order.ordered_at,
    } for order, definition in rows]
    _record_access(db, user.id, hospital_id, link, "viewed_medications", len(result))
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result


@router.get("/patients/{patient_id}/invoices", response_model=list[PatientPortalInvoiceRead])
def list_patient_invoices(patient_id: UUID, context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    link = _active_link(db, user.id, hospital_id, patient_id)
    _require_scope(link, "invoices")
    rows = db.scalars(select(Invoice).where(
        Invoice.hospital_id == hospital_id,
        Invoice.patient_id == patient_id,
        Invoice.status != "draft",
    ).order_by(Invoice.created_at.desc()).limit(300)).all()
    result = [{
        "id": invoice.id, "invoice_number": invoice.invoice_number,
        "currency": invoice.currency, "subtotal_total": invoice.subtotal_total,
        "amount_paid_total": invoice.amount_paid_total,
        "balance_due": invoice.subtotal_total - invoice.amount_paid_total,
        "status": invoice.status, "issued_at": invoice.issued_at,
        "created_at": invoice.created_at,
    } for invoice in rows]
    _record_access(db, user.id, hospital_id, link, "viewed_invoices", len(result))
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result


@router.get("/patients/{patient_id}/consents", response_model=list[PatientPortalConsentRead])
def list_patient_consents(patient_id: UUID, context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    link = _active_link(db, user.id, hospital_id, patient_id)
    _require_scope(link, "consents")
    rows = db.scalars(select(PatientConsent).where(
        PatientConsent.hospital_id == hospital_id,
        PatientConsent.patient_id == patient_id,
    ).order_by(PatientConsent.created_at.desc()).limit(200)).all()
    result = [{
        "id": item.id, "purpose": item.purpose, "scope": item.scope,
        "status": item.status, "basis_code": item.basis_code,
        "consent_method": item.consent_method, "granted_at": item.granted_at,
        "expires_at": item.expires_at, "withdrawn_at": item.withdrawn_at,
    } for item in rows]
    _record_access(db, user.id, hospital_id, link, "viewed_consents", len(result))
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result


@router.get("/links/{link_id}/access-history")
def list_patient_portal_access_history(link_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_portal_staff(db, user.id, hospital_id)
    link = db.scalar(select(PatientPortalLink).where(
        PatientPortalLink.id == link_id, PatientPortalLink.hospital_id == hospital_id,
    ))
    if link is None:
        raise HTTPException(status_code=404, detail={"code": "patient_portal_link_not_found"})
    rows = db.scalars(select(PatientPortalAccessEvent).where(
        PatientPortalAccessEvent.hospital_id == hospital_id,
        PatientPortalAccessEvent.portal_link_id == link.id,
    ).order_by(PatientPortalAccessEvent.created_at.desc()).limit(500)).all()
    return [{
        "id": row.id, "patient_id": row.patient_id, "portal_user_id": row.portal_user_id,
        "action": row.action, "resource_count": row.resource_count, "created_at": row.created_at,
    } for row in rows]
