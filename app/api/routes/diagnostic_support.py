from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.contracts import AICapability
from app.ai.patient_context import PatientContextDenied, load_authorized_patient_context
from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    AISession,
    AISessionMessage,
    ClinicalAISessionContext,
    ImagingProcedureDefinition,
    LaboratoryTestDefinition,
)
from app.models.clinical_taxonomy import ClinicalConcept
from app.models.diagnostic_support import (
    DiagnosticDifferentialSuggestion,
    DiagnosticSupportCase,
    DiagnosticTestConsideration,
)
from app.models.knowledge import MedicalKnowledgeDocument, MedicalKnowledgeSource
from app.schemas.diagnostic_support import (
    DiagnosticSupportCaseClose,
    DiagnosticSupportCaseCreate,
    DiagnosticSupportCaseRead,
    DiagnosticTestConsiderationCreate,
    DiagnosticTestConsiderationRead,
    DiagnosticTestConsiderationReview,
    DifferentialSuggestionCreate,
    DifferentialSuggestionRead,
    DifferentialSuggestionReview,
)

router = APIRouter(prefix="/ai/diagnostics", tags=["AI diagnostic support"])


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, user_id: UUID, hospital_id: UUID, action: str, resource_type: str, resource_id: UUID) -> None:
    write_audit_event(
        db,
        hospital_id=hospital_id,
        actor_user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        metadata={},
    )


def _source_message(
    db: Session, *, hospital_id: UUID, user_id: UUID, session_id: UUID,
    assistant_sequence: int, response_digest: str,
) -> AISessionMessage:
    message = db.scalar(select(AISessionMessage).where(
        AISessionMessage.hospital_id == hospital_id,
        AISessionMessage.owner_user_id == user_id,
        AISessionMessage.session_id == session_id,
        AISessionMessage.sequence_number == assistant_sequence,
        AISessionMessage.role == "assistant",
    ))
    metadata = message.metadata_json or {} if message is not None else {}
    if (
        message is None
        or metadata.get("response_digest") != response_digest
        or metadata.get("capability") != AICapability.CLINICAL_DECISION_SUPPORT.value
    ):
        raise HTTPException(status_code=409, detail={"code": "diagnostic_source_response_mismatch"})
    return message


def _validate_citations(message: AISessionMessage, citation_ids: list[str]) -> None:
    source_ids = set((message.metadata_json or {}).get("citation_ids", []))
    if not citation_ids or not set(citation_ids).issubset(source_ids):
        raise HTTPException(status_code=422, detail={"code": "diagnostic_evidence_citation_not_in_source_response"})


def _authorized_case(
    db: Session, *, user_id: UUID, hospital_id: UUID, case_id: UUID,
) -> tuple[DiagnosticSupportCase, AISessionMessage]:
    case = db.scalar(select(DiagnosticSupportCase).where(
        DiagnosticSupportCase.hospital_id == hospital_id,
        DiagnosticSupportCase.id == case_id,
        DiagnosticSupportCase.owner_user_id == user_id,
    ).with_for_update())
    if case is None:
        raise HTTPException(status_code=404, detail={"code": "diagnostic_support_case_not_found"})
    session_context = db.scalar(select(ClinicalAISessionContext).where(
        ClinicalAISessionContext.hospital_id == hospital_id,
        ClinicalAISessionContext.session_id == case.session_id,
        ClinicalAISessionContext.owner_user_id == user_id,
        ClinicalAISessionContext.status == "active",
    ))
    session_record = db.scalar(select(AISession).where(
        AISession.hospital_id == hospital_id,
        AISession.id == case.session_id,
        AISession.owner_user_id == user_id,
        AISession.status == "active",
        AISession.expires_at > datetime.now(timezone.utc),
    ))
    if session_context is None or session_record is None:
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
        raise HTTPException(status_code=403, detail={"code": "diagnostic_case_authorization_context_changed"})
    message = _source_message(
        db, hospital_id=hospital_id, user_id=user_id, session_id=case.session_id,
        assistant_sequence=case.source_assistant_sequence, response_digest=case.source_response_digest,
    )
    return case, message


@router.post("/cases", response_model=DiagnosticSupportCaseRead, status_code=status.HTTP_201_CREATED)
def create_diagnostic_support_case(
    payload: DiagnosticSupportCaseCreate,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    user, hospital_id = context
    session_context = db.scalar(select(ClinicalAISessionContext).where(
        ClinicalAISessionContext.hospital_id == hospital_id,
        ClinicalAISessionContext.session_id == payload.session_id,
        ClinicalAISessionContext.owner_user_id == user.id,
        ClinicalAISessionContext.status == "active",
    ))
    session_record = db.scalar(select(AISession).where(
        AISession.hospital_id == hospital_id,
        AISession.id == payload.session_id,
        AISession.owner_user_id == user.id,
        AISession.status == "active",
        AISession.expires_at > datetime.now(timezone.utc),
    ))
    if session_context is None or session_record is None:
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
    _source_message(
        db, hospital_id=hospital_id, user_id=user.id, session_id=payload.session_id,
        assistant_sequence=payload.assistant_sequence, response_digest=payload.response_digest,
    )
    case = DiagnosticSupportCase(
        hospital_id=hospital_id,
        session_id=payload.session_id,
        owner_user_id=user.id,
        patient_id=session_context.patient_id,
        encounter_id=session_context.encounter_id,
        consent_id=session_context.consent_id,
        assignment_id=session_context.assignment_id,
        source_assistant_sequence=payload.assistant_sequence,
        source_response_digest=payload.response_digest,
    )
    db.add(case)
    try:
        db.flush()
        _audit(db, user.id, hospital_id, "ai.diagnostic_case.created", "diagnostic_support_case", case.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        _restore_context(db, user.id, hospital_id)
        raise HTTPException(status_code=409, detail={"code": "diagnostic_case_already_exists_or_conflicts"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.get("/cases/{case_id}", response_model=DiagnosticSupportCaseRead)
def get_diagnostic_support_case(
    case_id: UUID, context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    case, _ = _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    return case


@router.get("/cases/{case_id}/differentials", response_model=list[DifferentialSuggestionRead])
def list_diagnostic_differentials(
    case_id: UUID, context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    return db.scalars(select(DiagnosticDifferentialSuggestion).where(
        DiagnosticDifferentialSuggestion.hospital_id == hospital_id,
        DiagnosticDifferentialSuggestion.case_id == case_id,
    ).order_by(DiagnosticDifferentialSuggestion.created_at.asc())).all()


@router.post("/cases/{case_id}/differentials", response_model=DifferentialSuggestionRead, status_code=status.HTTP_201_CREATED)
def add_diagnostic_differential(
    case_id: UUID, payload: DifferentialSuggestionCreate,
    context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    case, source_message = _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    if case.status != "open":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_case_closed"})
    _validate_citations(source_message, payload.evidence_citation_ids)
    now = datetime.now(timezone.utc)
    concept = db.scalar(select(ClinicalConcept).join(
        MedicalKnowledgeDocument, MedicalKnowledgeDocument.id == ClinicalConcept.document_id,
    ).join(
        MedicalKnowledgeSource, MedicalKnowledgeSource.id == MedicalKnowledgeDocument.source_id,
    ).where(
        ClinicalConcept.id == payload.concept_id,
        ClinicalConcept.document_id == payload.document_id,
        ClinicalConcept.concept_type == "disease",
        ClinicalConcept.code == payload.concept_code,
        func.lower(ClinicalConcept.preferred_term) == payload.display_name.casefold(),
        MedicalKnowledgeDocument.status == "approved",
        or_(MedicalKnowledgeDocument.effective_from.is_(None), MedicalKnowledgeDocument.effective_from <= now),
        or_(MedicalKnowledgeDocument.effective_to.is_(None), MedicalKnowledgeDocument.effective_to > now),
        or_(MedicalKnowledgeDocument.next_review_at.is_(None), MedicalKnowledgeDocument.next_review_at > now),
        MedicalKnowledgeSource.status == "active",
        or_(
            MedicalKnowledgeSource.scope == "global",
            (MedicalKnowledgeSource.scope == "hospital") & (MedicalKnowledgeSource.hospital_id == hospital_id),
        ),
    ))
    if concept is None:
        raise HTTPException(status_code=422, detail={"code": "differential_must_match_approved_effective_concept"})
    suggestion = DiagnosticDifferentialSuggestion(
        hospital_id=hospital_id,
        case_id=case.id,
        document_id=concept.document_id,
        concept_id=concept.id,
        concept_code=concept.code,
        display_name=concept.preferred_term,
        evidence_citation_ids=payload.evidence_citation_ids,
    )
    db.add(suggestion)
    try:
        db.flush()
        _audit(db, user.id, hospital_id, "ai.diagnostic_differential.added", "diagnostic_differential", suggestion.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        _restore_context(db, user.id, hospital_id)
        raise HTTPException(status_code=409, detail={"code": "diagnostic_differential_already_added"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(suggestion)
    return suggestion


@router.post("/cases/{case_id}/differentials/{suggestion_id}/review", response_model=DifferentialSuggestionRead)
def review_diagnostic_differential(
    case_id: UUID, suggestion_id: UUID, payload: DifferentialSuggestionReview,
    context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    case, _ = _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    if case.status != "open":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_case_closed"})
    suggestion = db.scalar(select(DiagnosticDifferentialSuggestion).where(
        DiagnosticDifferentialSuggestion.hospital_id == hospital_id,
        DiagnosticDifferentialSuggestion.case_id == case.id,
        DiagnosticDifferentialSuggestion.id == suggestion_id,
    ).with_for_update())
    if suggestion is None:
        raise HTTPException(status_code=404, detail={"code": "diagnostic_differential_not_found"})
    if suggestion.status != "proposed":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_differential_already_reviewed"})
    suggestion.status = payload.status
    suggestion.reviewed_by_user_id = user.id
    suggestion.reviewed_at = datetime.now(timezone.utc)
    suggestion.review_reference = payload.review_reference
    _audit(db, user.id, hospital_id, "ai.diagnostic_differential.reviewed", "diagnostic_differential", suggestion.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(suggestion)
    return suggestion


@router.get("/cases/{case_id}/tests", response_model=list[DiagnosticTestConsiderationRead])
def list_diagnostic_test_considerations(
    case_id: UUID, context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    return db.scalars(select(DiagnosticTestConsideration).where(
        DiagnosticTestConsideration.hospital_id == hospital_id,
        DiagnosticTestConsideration.case_id == case_id,
    ).order_by(DiagnosticTestConsideration.created_at.asc())).all()


@router.post("/cases/{case_id}/tests", response_model=DiagnosticTestConsiderationRead, status_code=status.HTTP_201_CREATED)
def add_diagnostic_test_consideration(
    case_id: UUID, payload: DiagnosticTestConsiderationCreate,
    context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    case, source_message = _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    if case.status != "open":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_case_closed"})
    _validate_citations(source_message, payload.evidence_citation_ids)
    if payload.test_domain == "laboratory":
        definition = db.scalar(select(LaboratoryTestDefinition).where(
            LaboratoryTestDefinition.hospital_id == hospital_id,
            LaboratoryTestDefinition.id == payload.laboratory_test_definition_id,
            LaboratoryTestDefinition.status == "active",
            LaboratoryTestDefinition.code == payload.test_code,
            func.lower(LaboratoryTestDefinition.name) == payload.test_name.casefold(),
        ))
    else:
        definition = db.scalar(select(ImagingProcedureDefinition).where(
            ImagingProcedureDefinition.hospital_id == hospital_id,
            ImagingProcedureDefinition.id == payload.imaging_procedure_definition_id,
            ImagingProcedureDefinition.status == "active",
            ImagingProcedureDefinition.code == payload.test_code,
            func.lower(ImagingProcedureDefinition.name) == payload.test_name.casefold(),
        ))
    if definition is None:
        raise HTTPException(status_code=422, detail={"code": "test_consideration_must_match_active_hospital_definition"})
    consideration = DiagnosticTestConsideration(
        hospital_id=hospital_id,
        case_id=case.id,
        test_domain=payload.test_domain,
        laboratory_test_definition_id=payload.laboratory_test_definition_id,
        imaging_procedure_definition_id=payload.imaging_procedure_definition_id,
        test_code=definition.code,
        test_name=definition.name,
        evidence_citation_ids=payload.evidence_citation_ids,
    )
    db.add(consideration)
    try:
        db.flush()
        _audit(db, user.id, hospital_id, "ai.diagnostic_test_consideration.added", "diagnostic_test_consideration", consideration.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        _restore_context(db, user.id, hospital_id)
        raise HTTPException(status_code=409, detail={"code": "diagnostic_test_consideration_already_added"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(consideration)
    return consideration


@router.post("/cases/{case_id}/tests/{consideration_id}/review", response_model=DiagnosticTestConsiderationRead)
def review_diagnostic_test_consideration(
    case_id: UUID, consideration_id: UUID, payload: DiagnosticTestConsiderationReview,
    context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    case, _ = _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    if case.status != "open":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_case_closed"})
    consideration = db.scalar(select(DiagnosticTestConsideration).where(
        DiagnosticTestConsideration.hospital_id == hospital_id,
        DiagnosticTestConsideration.case_id == case.id,
        DiagnosticTestConsideration.id == consideration_id,
    ).with_for_update())
    if consideration is None:
        raise HTTPException(status_code=404, detail={"code": "diagnostic_test_consideration_not_found"})
    if consideration.status != "proposed":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_test_consideration_already_reviewed"})
    consideration.status = payload.status
    consideration.reviewed_by_user_id = user.id
    consideration.reviewed_at = datetime.now(timezone.utc)
    consideration.review_reference = payload.review_reference
    _audit(db, user.id, hospital_id, "ai.diagnostic_test_consideration.reviewed", "diagnostic_test_consideration", consideration.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(consideration)
    return consideration


@router.post("/cases/{case_id}/close", response_model=DiagnosticSupportCaseRead)
def close_diagnostic_support_case(
    case_id: UUID, payload: DiagnosticSupportCaseClose,
    context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    case, _ = _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    if case.status != "open":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_case_already_closed"})
    pending_differentials = db.scalar(select(func.count(DiagnosticDifferentialSuggestion.id)).where(
        DiagnosticDifferentialSuggestion.hospital_id == hospital_id,
        DiagnosticDifferentialSuggestion.case_id == case.id,
        DiagnosticDifferentialSuggestion.status == "proposed",
    )) or 0
    pending_tests = db.scalar(select(func.count(DiagnosticTestConsideration.id)).where(
        DiagnosticTestConsideration.hospital_id == hospital_id,
        DiagnosticTestConsideration.case_id == case.id,
        DiagnosticTestConsideration.status == "proposed",
    )) or 0
    if pending_differentials or pending_tests:
        raise HTTPException(status_code=409, detail={"code": "all_diagnostic_suggestions_must_be_reviewed_before_closure"})
    case.status = "closed"
    case.closure_reference = payload.closure_reference
    case.closed_by_user_id = user.id
    case.closed_at = datetime.now(timezone.utc)
    _audit(db, user.id, hospital_id, "ai.diagnostic_case.closed", "diagnostic_support_case", case.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case
