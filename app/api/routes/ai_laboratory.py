from datetime import date, datetime, timezone
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.contracts import AICapability
from app.ai.patient_context import PatientContextDenied, load_authorized_patient_context
from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import AISession, AISessionMessage, ClinicalAISessionContext, Patient
from app.models.ai_laboratory import AILaboratoryInterpretationCase
from app.models.laboratory import LaboratoryOrder, LaboratorySpecimen, LaboratoryResult, LaboratoryTestDefinition
from app.models.clinical_taxonomy import ClinicalConcept, LaboratoryReferenceInterval
from app.models.knowledge import MedicalKnowledgeDocument, MedicalKnowledgeSource
from app.schemas.ai_laboratory import (
    AILaboratoryInterpretationCreate, AILaboratoryInterpretationRead,
    AILaboratoryInterpretationReview,
)

router = APIRouter(prefix="/ai/laboratory", tags=["AI laboratory assistant"])


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _reference_interval_context(
    db: Session, *, hospital_id: UUID, patient_id: UUID,
    test_definition_id: UUID, specimen_type: str, unit: str | None,
    value_numeric, now: datetime,
) -> dict | None:
    """Return one unambiguous, current, context-matched governed interval; never guess."""
    if unit is None:
        return None
    patient = db.scalar(select(Patient).where(
        Patient.hospital_id == hospital_id, Patient.id == patient_id, Patient.status == "active",
    ))
    test = db.scalar(select(LaboratoryTestDefinition).where(
        LaboratoryTestDefinition.hospital_id == hospital_id,
        LaboratoryTestDefinition.id == test_definition_id,
        LaboratoryTestDefinition.status == "active",
    ))
    if patient is None or test is None:
        return None
    normalized_name = " ".join(re.sub(r"[^a-z0-9]+", " ", test.name.casefold()).split())
    concept = db.scalar(select(ClinicalConcept).where(
        ClinicalConcept.concept_type == "laboratory_test",
        ClinicalConcept.normalized_term == normalized_name,
    ))
    if concept is None:
        return None
    age_days = (now.date() - patient.date_of_birth).days if patient.date_of_birth else None
    sex = patient.administrative_sex.casefold() if patient.administrative_sex else None
    rows = db.execute(
        select(LaboratoryReferenceInterval, MedicalKnowledgeDocument, MedicalKnowledgeSource)
        .join(MedicalKnowledgeDocument, MedicalKnowledgeDocument.id == LaboratoryReferenceInterval.document_id)
        .join(MedicalKnowledgeSource, MedicalKnowledgeSource.id == MedicalKnowledgeDocument.source_id)
        .where(
            LaboratoryReferenceInterval.test_concept_id == concept.id,
            LaboratoryReferenceInterval.document_id == concept.document_id,
            LaboratoryReferenceInterval.unit == unit,
            MedicalKnowledgeDocument.status == "approved",
            MedicalKnowledgeDocument.reviewed_at.is_not(None),
            MedicalKnowledgeDocument.next_review_at > now,
            or_(MedicalKnowledgeDocument.effective_from.is_(None), MedicalKnowledgeDocument.effective_from <= now),
            or_(MedicalKnowledgeDocument.effective_to.is_(None), MedicalKnowledgeDocument.effective_to > now),
            MedicalKnowledgeSource.status == "active",
            or_(MedicalKnowledgeSource.scope == "global", MedicalKnowledgeSource.hospital_id == hospital_id),
        )
    ).all()
    candidates = []
    for interval, document, source in rows:
        if interval.specimen and interval.specimen.casefold() != specimen_type.casefold():
            continue
        if interval.method and (not test.method or interval.method.casefold() != test.method.casefold()):
            continue
        if interval.sex_context and (sex is None or interval.sex_context.casefold() != sex):
            continue
        if interval.pregnancy_context is not None or interval.population_context is not None:
            continue
        if age_days is None:
            if interval.age_min_days is not None or interval.age_max_days is not None:
                continue
        elif ((interval.age_min_days is not None and age_days < interval.age_min_days)
              or (interval.age_max_days is not None and age_days > interval.age_max_days)):
            continue
        specificity = sum((
            interval.specimen is not None, interval.method is not None,
            interval.sex_context is not None, interval.age_min_days is not None or interval.age_max_days is not None,
        ))
        candidates.append((specificity, interval, document, source))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    best = [item for item in candidates if item[0] == candidates[0][0]]
    if len(best) != 1:
        return None
    _, interval, document, source = best[0]
    comparison = "not_comparable"
    if value_numeric is not None:
        below = interval.lower_bound is not None and value_numeric < interval.lower_bound
        above = interval.upper_bound is not None and value_numeric > interval.upper_bound
        comparison = "below_interval" if below else "above_interval" if above else "within_interval"
    return {
        "interval_id": str(interval.id),
        "knowledge_document_id": str(document.id),
        "document_title": document.title,
        "document_version": document.version,
        "source_title": source.title,
        "publisher": source.publisher,
        "canonical_url": source.canonical_url,
        "evidence_grade": document.evidence_grade,
        "reviewed_at": document.reviewed_at.isoformat(),
        "next_review_at": document.next_review_at.isoformat(),
        "unit": interval.unit,
        "lower_bound": str(interval.lower_bound) if interval.lower_bound is not None else None,
        "upper_bound": str(interval.upper_bound) if interval.upper_bound is not None else None,
        "specimen": interval.specimen,
        "method": interval.method,
        "age_min_days": interval.age_min_days,
        "age_max_days": interval.age_max_days,
        "sex_context": interval.sex_context,
        "interpretation_notes": interval.interpretation_notes,
        "numeric_comparison": comparison,
        "comparison_notice": "Reference comparison only; does not replace the laboratory's verified flag or clinician interpretation.",
    }


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
    now = datetime.now(timezone.utc)
    for result, specimen, order in sorted(rows, key=lambda item: str(item[0].id)):
        test = db.scalar(select(LaboratoryTestDefinition).where(
            LaboratoryTestDefinition.hospital_id == hospital_id,
            LaboratoryTestDefinition.id == order.test_definition_id,
        ))
        interval_context = _reference_interval_context(
            db, hospital_id=hospital_id, patient_id=session_context.patient_id,
            test_definition_id=order.test_definition_id, specimen_type=specimen.specimen_type,
            unit=result.unit, value_numeric=result.value_numeric, now=now,
        )
        snapshot.append({
            "result_id": str(result.id), "order_id": str(order.id),
            "test_definition_id": str(order.test_definition_id),
            "test_code": test.code if test else None,
            "test_name": test.name if test else None,
            "accession_number": specimen.accession_number,
            "specimen_type": specimen.specimen_type,
            "value_text": result.value_text,
            "value_numeric": str(result.value_numeric) if result.value_numeric is not None else None,
            "unit": result.unit, "abnormality": result.abnormality,
            "interpretation_note": result.interpretation_note,
            "critical_flag": result.critical_flag,
            "verified_at": result.verified_at.isoformat(),
            "reference_interval_context": interval_context,
        })
    case = AILaboratoryInterpretationCase(
        hospital_id=hospital_id, session_id=payload.session_id, owner_user_id=user.id,
        patient_id=session_context.patient_id, encounter_id=session_context.encounter_id,
        consent_id=session_context.consent_id, assignment_id=session_context.assignment_id,
        source_assistant_sequence=payload.assistant_sequence, source_response_digest=payload.response_digest,
        laboratory_result_ids=[str(value) for value in sorted(set(payload.laboratory_result_ids), key=str)],
        evidence_citation_ids=sorted(set(metadata.get("citation_ids", []))) if isinstance(metadata.get("citation_ids", []), list) else [],
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
