import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.contracts import AICapability
from app.ai.patient_context import PatientContextDenied, load_authorized_patient_context
from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import AISession, AISessionMessage, ClinicalAISessionContext, MedicationDefinition, MedicationOrder
from app.models.ai_pharmacy import AIPharmacySafetyCase
from app.schemas.ai_pharmacy import AIPharmacySafetyCreate, AIPharmacySafetyRead, AIPharmacySafetyReview

router = APIRouter(prefix="/ai/pharmacy", tags=["AI pharmacy assistant"])


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _patient_authorized(db: Session, *, user_id: UUID, hospital_id: UUID, patient_id: UUID,
                        encounter_id: UUID, consent_id: UUID, assignment_id: UUID) -> None:
    try:
        authorized = load_authorized_patient_context(
            db, hospital_id=hospital_id, actor_user_id=user_id,
            patient_id=patient_id, encounter_id=encounter_id)
    except PatientContextDenied as exc:
        raise HTTPException(status_code=403, detail={"code": str(exc)}) from exc
    if authorized.consent_id != consent_id or authorized.assignment_id != assignment_id:
        raise HTTPException(status_code=403, detail={"code": "pharmacy_case_authorization_context_changed"})


def _order_digest(order: MedicationOrder, definition: MedicationDefinition) -> str:
    payload = {
        "order_id": str(order.id), "patient_id": str(order.patient_id), "encounter_id": str(order.encounter_id),
        "definition_id": str(definition.id), "generic_name": definition.generic_name,
        "brand_name": definition.brand_name, "active_ingredient": definition.active_ingredient,
        "strength_label": definition.strength_label, "dosage_form": definition.dosage_form, "definition_status": definition.status,
        "approved_at": definition.approved_at.isoformat() if definition.approved_at else None,
        "dose_text": order.dose_text, "route": order.route, "frequency_text": order.frequency_text,
        "duration_days": order.duration_days, "quantity_prescribed": str(order.quantity_prescribed),
        "quantity_unit": order.quantity_unit, "refills": order.refills, "indication": order.indication,
        "instructions": order.instructions, "status": order.status,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _authorized_case(db: Session, *, user_id: UUID, hospital_id: UUID, case_id: UUID) -> AIPharmacySafetyCase:
    case = db.scalar(select(AIPharmacySafetyCase).where(
        AIPharmacySafetyCase.hospital_id == hospital_id, AIPharmacySafetyCase.id == case_id,
        AIPharmacySafetyCase.owner_user_id == user_id).with_for_update())
    if case is None:
        raise HTTPException(status_code=404, detail={"code": "pharmacy_safety_case_not_found"})
    context = db.scalar(select(ClinicalAISessionContext).where(
        ClinicalAISessionContext.hospital_id == hospital_id, ClinicalAISessionContext.session_id == case.session_id,
        ClinicalAISessionContext.owner_user_id == user_id, ClinicalAISessionContext.status == "active"))
    session = db.scalar(select(AISession).where(
        AISession.hospital_id == hospital_id, AISession.id == case.session_id,
        AISession.owner_user_id == user_id, AISession.status == "active",
        AISession.expires_at > datetime.now(timezone.utc)))
    if context is None or session is None:
        raise HTTPException(status_code=403, detail={"code": "active_clinical_ai_session_required"})
    if (context.patient_id, context.encounter_id, context.consent_id, context.assignment_id) != (
        case.patient_id, case.encounter_id, case.consent_id, case.assignment_id):
        raise HTTPException(status_code=403, detail={"code": "pharmacy_session_context_mismatch"})
    _patient_authorized(db, user_id=user_id, hospital_id=hospital_id, patient_id=case.patient_id,
        encounter_id=case.encounter_id, consent_id=case.consent_id, assignment_id=case.assignment_id)
    message = db.scalar(select(AISessionMessage).where(
        AISessionMessage.hospital_id == hospital_id, AISessionMessage.owner_user_id == user_id,
        AISessionMessage.session_id == case.session_id,
        AISessionMessage.sequence_number == case.source_assistant_sequence, AISessionMessage.role == "assistant"))
    metadata = (message.metadata_json or {}) if message else {}
    if message is None or metadata.get("response_digest") != case.source_response_digest or metadata.get("capability") != AICapability.MEDICATION_SAFETY.value:
        raise HTTPException(status_code=409, detail={"code": "pharmacy_source_response_mismatch"})
    order = db.scalar(select(MedicationOrder).where(
        MedicationOrder.hospital_id == hospital_id, MedicationOrder.id == case.order_id))
    definition = db.scalar(select(MedicationDefinition).where(
        MedicationDefinition.hospital_id == hospital_id,
        MedicationDefinition.id == order.medication_definition_id)) if order else None
    if order is None or definition is None or _order_digest(order, definition) != case.order_digest:
        case.status = "stale"
        db.commit()
        _restore_context(db, user_id, hospital_id)
        raise HTTPException(status_code=409, detail={"code": "source_medication_order_changed_case_stale"})
    return case


@router.post("/safety-cases", response_model=AIPharmacySafetyRead, status_code=status.HTTP_201_CREATED)
def create_pharmacy_safety_case(payload: AIPharmacySafetyCreate, context=Depends(get_current_context),
                                db: Session = Depends(get_db)):
    user, hospital_id = context
    session_context = db.scalar(select(ClinicalAISessionContext).where(
        ClinicalAISessionContext.hospital_id == hospital_id, ClinicalAISessionContext.session_id == payload.session_id,
        ClinicalAISessionContext.owner_user_id == user.id, ClinicalAISessionContext.status == "active"))
    session = db.scalar(select(AISession).where(
        AISession.hospital_id == hospital_id, AISession.id == payload.session_id,
        AISession.owner_user_id == user.id, AISession.status == "active",
        AISession.expires_at > datetime.now(timezone.utc)))
    if session_context is None or session is None:
        raise HTTPException(status_code=404, detail={"code": "active_clinical_ai_session_not_found"})
    _patient_authorized(db, user_id=user.id, hospital_id=hospital_id, patient_id=session_context.patient_id,
        encounter_id=session_context.encounter_id, consent_id=session_context.consent_id,
        assignment_id=session_context.assignment_id)
    message = db.scalar(select(AISessionMessage).where(
        AISessionMessage.hospital_id == hospital_id, AISessionMessage.owner_user_id == user.id,
        AISessionMessage.session_id == payload.session_id,
        AISessionMessage.sequence_number == payload.assistant_sequence, AISessionMessage.role == "assistant"))
    metadata = (message.metadata_json or {}) if message else {}
    if message is None or metadata.get("response_digest") != payload.response_digest or metadata.get("capability") != AICapability.MEDICATION_SAFETY.value:
        raise HTTPException(status_code=409, detail={"code": "pharmacy_source_response_mismatch"})
    order = db.scalar(select(MedicationOrder).where(
        MedicationOrder.hospital_id == hospital_id, MedicationOrder.id == payload.order_id,
        MedicationOrder.patient_id == session_context.patient_id,
        MedicationOrder.encounter_id == session_context.encounter_id,
        MedicationOrder.status != "cancelled"))
    if order is None:
        raise HTTPException(status_code=422, detail={"code": "active_patient_encounter_medication_order_required"})
    definition = db.scalar(select(MedicationDefinition).where(
        MedicationDefinition.hospital_id == hospital_id, MedicationDefinition.id == order.medication_definition_id,
        MedicationDefinition.status == "active"))
    if definition is None:
        raise HTTPException(status_code=422, detail={"code": "active_approved_medication_definition_required"})
    digest = _order_digest(order, definition)
    if digest != payload.order_digest:
        raise HTTPException(status_code=409, detail={"code": "medication_order_digest_mismatch"})
    snapshot = {
        "order_id": str(order.id), "medication_definition_id": str(definition.id),
        "generic_name": definition.generic_name, "brand_name": definition.brand_name,
        "active_ingredient": definition.active_ingredient, "strength_label": definition.strength_label,
        "dosage_form": definition.dosage_form, "definition_status": definition.status, "dose_text": order.dose_text, "route": order.route,
        "frequency_text": order.frequency_text, "duration_days": order.duration_days,
        "quantity_prescribed": str(order.quantity_prescribed), "quantity_unit": order.quantity_unit,
        "refills": order.refills, "indication": order.indication, "instructions": order.instructions,
        "order_status": order.status, "ordered_at": order.ordered_at.isoformat(),
        "evidence_boundary": "Only evidence explicitly attached to the source assistant response may support safety claims. Missing allergy, interaction, renal, hepatic, pregnancy and monitoring context must be stated as unknown.",
    }
    case = AIPharmacySafetyCase(
        hospital_id=hospital_id, session_id=payload.session_id, owner_user_id=user.id,
        patient_id=session_context.patient_id, encounter_id=session_context.encounter_id,
        consent_id=session_context.consent_id, assignment_id=session_context.assignment_id,
        order_id=order.id, order_digest=digest, order_snapshot=snapshot,
        source_assistant_sequence=payload.assistant_sequence, source_response_digest=payload.response_digest)
    db.add(case)
    try:
        db.flush()
        write_audit_event(db, hospital_id=hospital_id, actor_user_id=user.id,
            action="ai.pharmacy_safety_case.created", resource_type="ai_pharmacy_safety_case",
            resource_id=str(case.id), metadata={"order_status": order.status})
        db.commit()
    except IntegrityError:
        db.rollback()
        _restore_context(db, user.id, hospital_id)
        raise HTTPException(status_code=409, detail={"code": "pharmacy_safety_case_already_exists_or_conflicts"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.get("/safety-cases/{case_id}", response_model=AIPharmacySafetyRead)
def get_pharmacy_safety_case(case_id: UUID, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    return _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)


@router.post("/safety-cases/{case_id}/review", response_model=AIPharmacySafetyRead)
def review_pharmacy_safety_case(case_id: UUID, payload: AIPharmacySafetyReview,
                                context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    case = _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    if case.status != "pending_review":
        raise HTTPException(status_code=409, detail={"code": "pharmacy_safety_case_not_pending_review"})
    case.status = "reviewed"
    case.review_decision = payload.decision
    case.review_reference = payload.review_reference
    case.review_note_reference = payload.note_reference
    case.reviewed_by_user_id = user.id
    case.reviewed_at = datetime.now(timezone.utc)
    write_audit_event(db, hospital_id=hospital_id, actor_user_id=user.id,
        action="ai.pharmacy_safety_case.reviewed", resource_type="ai_pharmacy_safety_case",
        resource_id=str(case.id), metadata={"decision": payload.decision})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case
