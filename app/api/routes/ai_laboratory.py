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
from app.models import AISession, AISessionMessage, ClinicalAISessionContext
from app.models.ai_laboratory import AILaboratoryInterpretationCase
from app.models.laboratory import LaboratoryOrder, LaboratorySpecimen, LaboratoryResult
from app.schemas.ai_laboratory import (
    AILaboratoryInterpretationCreate, AILaboratoryInterpretationRead,
    AILaboratoryInterpretationReview,
)

router = APIRouter(prefix="/ai/laboratory", tags=["AI laboratory assistant"])


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _authorize(db: Session, *, user_id: UUID, hospital_id: UUID, case: AILaboratoryInterpretationCase) -> None:
    session_context = db.scalar(select(ClinicalAISessionContext).where(
        ClinicalAISessionContext.hospital_id == hospital_id,
        ClinicalAISessionContext.session_id == case.session_id,
        ClinicalAISessionContext.owner_user_id == user_id,
        ClinicalAISessionContext.status == "active",
    ))
    session = db.scalar(select(AISession).where(
        AISession.hospital_id == hospital_id, AISession.id == case.session_id,
        AISession.owner_user_id == user_id, AISession.status == "active",
        AISession.expires_at > datetime.now(timezone.utc),
    ))
    if session_context is None or session is None:
        raise HTTPException(status_code=403, detail={"code": "active_clinical_ai_session_required"})
    try:
        authorized = load_authorized_patient_context(
            db, hospital_id=hospital_id, actor_user_id=user_id,
            patient_id=case.patient_id, encounter_id=case.encounter_id,
        )
    except PatientContextDenied as exc:
        raise HTTPException(status_code=403, detail={"code": str(exc)}) from exc
    if (
        session_context.patient_id != case.patient_id
        or session_context.encounter_id != case.encounter_id
        or session_context.consent_id != case.consent_id
        or session_context.assignment_id != case.assignment_id
        or authorized.consent_id != case.consent_id
        or authorized.assignment_id != case.assignment_id
    ):
        raise HTTPException(status_code=403, detail={"code": "laboratory_case_authorization_context_changed"})


def _case(db: Session, *, user_id: UUID, hospital_id: UUID, case_id: UUID):
    case = db.scalar(select(AILaboratoryInterpretationCase).where(
        AILaboratoryInterpretationCase.hospital_id == hospital_id,
        AILaboratoryInterpretationCase.id == case_id,
        AILaboratoryInterpretationCase.owner_user_id == user_id,
    ).with_for_update())
    if case is None:
        raise HTTPException(status_code=404, detail={"code": "laboratory_interpretation_case_not_found"})
    _authorize(db, user_id=user_id, hospital_id=hospital_id, case=case)
    message = db.scalar(select(AISessionMessage).where(
        AISessionMessage.hospital_id == hospital_id,
        AISessionMessage.owner_user_id == user_id,
        AISessionMessage.session_id == case.session_id,
        AISessionMessage.sequence_number == case.source_assistant_sequence,
        AISessionMessage.role == "assistant",
    ))
    metadata = (message.metadata_json or {}) if message else {}
    if message is None or metadata.get("response_digest") != case.source_response_digest or metadata.get("capability") != AICapability.LAB_INTERPRETATION.value:
        raise HTTPException(status_code=409, detail={"code": "laboratory_source_response_mismatch"})
    return case


@router.post("/interpretations", response_model=AILaboratoryInterpretationRead, status_code=status.HTTP_201_CREATED)
def create_laboratory_interpretation(
    payload: AILaboratoryInterpretationCreate,
    context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    session_context = db.scalar(select(ClinicalAISessionContext).where(
        ClinicalAISessionContext.hospital_id == hospital_id,
        ClinicalAISessionContext.session_id == payload.session_id,
        ClinicalAISessionContext.owner_user_id == user.id,
        ClinicalAISessionContext.status == "active",
    ))
    session = db.scalar(select(AISession).where(
        AISession.hospital_id == hospital_id, AISession.id == payload.session_id,
        AISession.owner_user_id == user.id, AISession.status == "active",
        AISession.expires_at > datetime.now(timezone.utc),
    ))
    if session_context is None or session is None:
        raise HTTPException(status_code=404, detail={"code": "active_clinical_ai_session_not_found"})
    try:
        authorized = load_authorized_patient_context(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            patient_id=session_context.patient_id, encounter_id=session_context.encounter_id,
        )
    except PatientContextDenied as exc:
        raise HTTPException(status_code=403, detail={"code": str(exc)}) from exc
    if authorized.consent_id != session_context.consent_id or authorized.assignment_id != session_context.assignment_id:
        raise HTTPException(status_code=403, detail={"code": "clinical_ai_session_authorization_context_changed"})
    message = db.scalar(select(AISessionMessage).where(
        AISessionMessage.hospital_id == hospital_id, AISessionMessage.owner_user_id == user.id,
        AISessionMessage.session_id == payload.session_id,
        AISessionMessage.sequence_number == payload.assistant_sequence, AISessionMessage.role == "assistant",
    ))
    metadata = (message.metadata_json or {}) if message else {}
    if message is None or metadata.get("response_digest") != payload.response_digest or metadata.get("capability") != AICapability.LAB_INTERPRETATION.value:
        raise HTTPException(status_code=409, detail={"code": "laboratory_source_response_mismatch"})

    rows = db.execute(
        select(LaboratoryResult, LaboratorySpecimen, LaboratoryOrder, )
        .join(LaboratorySpecimen, (LaboratorySpecimen.hospital_id == LaboratoryResult.hospital_id) & (LaboratorySpecimen.id == LaboratoryResult.specimen_id))
        .join(LaboratoryOrder, (LaboratoryOrder.hospital_id == LaboratorySpecimen.hospital_id) & (LaboratoryOrder.id == LaboratorySpecimen.order_id))
        .where(
            LaboratoryResult.hospital_id == hospital_id,
            LaboratoryResult.id.in_(payload.laboratory_result_ids),
            LaboratoryResult.status == "final",
            LaboratoryResult.verified_by_user_id.is_not(None),
            LaboratoryResult.verified_at.is_not(None),
            LaboratorySpecimen.status == "completed",
            LaboratoryOrder.status == "completed",
            LaboratoryOrder.patient_id == session_context.patient_id,
            LaboratoryOrder.encounter_id == session_context.encounter_id,
        )
    ).all()
    if len(rows) != len(set(payload.laboratory_result_ids)):
        raise HTTPException(status_code=422, detail={"code": "only_verified_final_results_for_bound_patient_encounter_are_eligible"})
    snapshot = []
    for result, specimen, order in rows:
        snapshot.append({
            "result_id": str(result.id), "order_id": str(order.id),
            "test_definition_id": str(order.test_definition_id),
            "accession_number": specimen.accession_number,
            "specimen_type": specimen.specimen_type,
            "value_text": result.value_text,
            "value_numeric": str(result.value_numeric) if result.value_numeric is not None else None,
            "unit": result.unit, "abnormality": result.abnormality,
            "interpretation_note": result.interpretation_note,
            "critical_flag": result.critical_flag,
            "verified_at": result.verified_at.isoformat(),
        })
    case = AILaboratoryInterpretationCase(
        hospital_id=hospital_id, session_id=payload.session_id, owner_user_id=user.id,
        patient_id=session_context.patient_id, encounter_id=session_context.encounter_id,
        consent_id=session_context.consent_id, assignment_id=session_context.assignment_id,
        source_assistant_sequence=payload.assistant_sequence, source_response_digest=payload.response_digest,
        laboratory_result_ids=[str(value) for value in payload.laboratory_result_ids],
        result_snapshot=snapshot,
    )
    db.add(case)
    try:
        db.flush()
        write_audit_event(db, hospital_id=hospital_id, actor_user_id=user.id,
            action="ai.laboratory_interpretation.created", resource_type="ai_laboratory_interpretation_case",
            resource_id=str(case.id), metadata={"result_count": len(snapshot)})
        db.commit()
    except IntegrityError:
        db.rollback()
        _restore_context(db, user.id, hospital_id)
        raise HTTPException(status_code=409, detail={"code": "laboratory_interpretation_already_exists_or_conflicts"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.get("/interpretations/{case_id}", response_model=AILaboratoryInterpretationRead)
def get_laboratory_interpretation(
    case_id: UUID, context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    return _case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)


@router.post("/interpretations/{case_id}/review", response_model=AILaboratoryInterpretationRead)
def review_laboratory_interpretation(
    case_id: UUID, payload: AILaboratoryInterpretationReview,
    context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    case = _case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    if case.status != "pending_review":
        raise HTTPException(status_code=409, detail={"code": "laboratory_interpretation_already_reviewed"})
    case.status = "reviewed"
    case.review_decision = payload.decision
    case.review_reference = payload.review_reference
    case.review_note_reference = payload.note_reference
    case.reviewed_by_user_id = user.id
    case.reviewed_at = datetime.now(timezone.utc)
    write_audit_event(db, hospital_id=hospital_id, actor_user_id=user.id,
        action="ai.laboratory_interpretation.reviewed", resource_type="ai_laboratory_interpretation_case",
        resource_id=str(case.id), metadata={"decision": payload.decision})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case
