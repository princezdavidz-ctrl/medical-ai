from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    AISession, AISessionMessage, ClinicalAISessionContext, ClinicalConcept,
    HospitalMembership, ImagingProcedureDefinition, LaboratoryTestDefinition,
)
from app.models.diagnostic_support import (
    DiagnosticDifferential, DiagnosticSupportCase, DiagnosticTestConsideration,
)
from app.schemas.diagnostic_support import (
    DiagnosticDifferentialCreate, DiagnosticDifferentialRead,
    DiagnosticDifferentialReview, DiagnosticSupportCaseClose,
    DiagnosticSupportCaseCreate, DiagnosticSupportCaseRead,
    DiagnosticTestConsiderationCreate, DiagnosticTestConsiderationRead,
    DiagnosticTestConsiderationReview,
)
from app.services.patient_context import PatientContextDenied, load_authorized_patient_context

router = APIRouter(prefix="/diagnostic-support", tags=["AI diagnostic support"])


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource_type: str, resource_id: UUID, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource_type, resource_id=str(resource_id), metadata=metadata or {},
    )


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _authorized_session(db: Session, user_id: UUID, hospital_id: UUID, session_id: UUID) -> ClinicalAISessionContext:
    context = db.scalar(select(ClinicalAISessionContext).where(
        ClinicalAISessionContext.hospital_id == hospital_id,
        ClinicalAISessionContext.session_id == session_id,
        ClinicalAISessionContext.owner_user_id == user_id,
        ClinicalAISessionContext.status == "active",
    ))
    session = db.scalar(select(AISession).where(
        AISession.hospital_id == hospital_id,
        AISession.id == session_id,
        AISession.owner_user_id == user_id,
        AISession.status == "active",
        AISession.expires_at > datetime.now(timezone.utc),
    ))
    if context is None or session is None:
        raise HTTPException(status_code=404, detail={"code": "active_clinical_ai_session_not_found"})
    try:
        authorized = load_authorized_patient_context(
            db, hospital_id=hospital_id, actor_user_id=user_id,
            patient_id=context.patient_id, encounter_id=context.encounter_id,
        )
    except PatientContextDenied as exc:
        raise HTTPException(status_code=403, detail={"code": str(exc)}) from exc
    if authorized.consent_id != context.consent_id or authorized.assignment_id != context.assignment_id:
        raise HTTPException(status_code=403, detail={"code": "clinical_ai_session_authorization_context_changed"})
    return context


def _case(db: Session, hospital_id: UUID, user_id: UUID, case_id: UUID, lock: bool = False) -> DiagnosticSupportCase:
    query = select(DiagnosticSupportCase).where(
        DiagnosticSupportCase.hospital_id == hospital_id,
        DiagnosticSupportCase.id == case_id,
        DiagnosticSupportCase.created_by_user_id == user_id,
    )
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "diagnostic_support_case_not_found"})
    _authorized_session(db, user_id, hospital_id, item.session_id)
    return item


def _source_message(db: Session, context: ClinicalAISessionContext, user_id: UUID, sequence: int, digest: str, citations: list[str]) -> None:
    message = db.scalar(select(AISessionMessage).where(
        AISessionMessage.hospital_id == context.hospital_id,
        AISessionMessage.session_id == context.session_id,
        AISessionMessage.owner_user_id == user_id,
        AISessionMessage.sequence_number == sequence,
        AISessionMessage.role == "assistant",
    ))
    if message is None or message.metadata_json.get("response_digest") != digest:
        raise HTTPException(status_code=409, detail={"code": "diagnostic_suggestion_source_response_mismatch"})
    approved_citations = set(message.metadata_json.get("citation_ids", []))
    if not set(citations).issubset(approved_citations):
        raise HTTPException(status_code=422, detail={"code": "diagnostic_suggestion_citation_not_in_source_response"})


@router.post("/cases", response_model=DiagnosticSupportCaseRead, status_code=status.HTTP_201_CREATED)
def create_diagnostic_support_case(payload: DiagnosticSupportCaseCreate, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    session_context = _authorized_session(db, user.id, hospital_id, payload.session_id)
    case = DiagnosticSupportCase(
        hospital_id=hospital_id, patient_id=session_context.patient_id,
        encounter_id=session_context.encounter_id, session_id=session_context.session_id,
        created_by_user_id=user.id, problem_representation=payload.problem_representation,
        known_findings=payload.known_findings, missing_information=payload.missing_information,
        red_flags=payload.red_flags,
    )
    db.add(case)
    db.flush()
    _audit(db, hospital_id, user.id, "diagnostic_support.case_created", "diagnostic_support_case", case.id)
    result = DiagnosticSupportCaseRead.model_validate(case)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result


@router.get("/cases", response_model=list[DiagnosticSupportCaseRead])
def list_diagnostic_support_cases(context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    items = db.scalars(select(DiagnosticSupportCase).where(
        DiagnosticSupportCase.hospital_id == hospital_id,
        DiagnosticSupportCase.created_by_user_id == user.id,
    ).order_by(DiagnosticSupportCase.created_at.desc()).limit(200)).all()
    visible = []
    for item in items:
        try:
            _authorized_session(db, user.id, hospital_id, item.session_id)
        except HTTPException:
            continue
        visible.append(item)
    return visible


@router.get("/cases/{case_id}", response_model=DiagnosticSupportCaseRead)
def get_diagnostic_support_case(case_id: UUID, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    return _case(db, hospital_id, user.id, case_id)


@router.post("/cases/{case_id}/differentials", response_model=DiagnosticDifferentialRead, status_code=status.HTTP_201_CREATED)
def add_diagnostic_differential(case_id: UUID, payload: DiagnosticDifferentialCreate, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    case = _case(db, hospital_id, user.id, case_id, lock=True)
    if case.status == "closed":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_support_case_closed"})
    concept = db.scalar(select(ClinicalConcept).where(
        ClinicalConcept.code == payload.concept_code,
        ClinicalConcept.concept_type.in_(("disease", "symptom", "finding")),
    ))
    if concept is None or concept.preferred_term.casefold() != payload.display_name.casefold():
        raise HTTPException(status_code=422, detail={"code": "approved_clinical_concept_code_and_name_required"})
    session_context = _authorized_session(db, user.id, hospital_id, case.session_id)
    _source_message(db, session_context, user.id, payload.source_sequence, payload.source_digest, payload.evidence_citation_ids)
    item = DiagnosticDifferential(
        hospital_id=hospital_id, case_id=case.id, concept_code=payload.concept_code,
        display_name=concept.preferred_term, rationale=payload.rationale,
        source_sequence=payload.source_sequence, source_digest=payload.source_digest,
        evidence_citation_ids=payload.evidence_citation_ids, entered_by_user_id=user.id,
    )
    db.add(item)
    case.status = "under_review"
    db.flush()
    _audit(db, hospital_id, user.id, "diagnostic_support.differential_added", "diagnostic_differential", item.id)
    result = DiagnosticDifferentialRead.model_validate(item)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result


@router.post("/cases/{case_id}/test-considerations", response_model=DiagnosticTestConsiderationRead, status_code=status.HTTP_201_CREATED)
def add_diagnostic_test_consideration(case_id: UUID, payload: DiagnosticTestConsiderationCreate, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    case = _case(db, hospital_id, user.id, case_id, lock=True)
    if case.status == "closed":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_support_case_closed"})
    if payload.modality == "laboratory":
        test = db.scalar(select(LaboratoryTestDefinition).where(
            LaboratoryTestDefinition.hospital_id == hospital_id,
            LaboratoryTestDefinition.code == payload.test_code,
            LaboratoryTestDefinition.status == "active",
        ))
    else:
        test = db.scalar(select(ImagingProcedureDefinition).where(
            ImagingProcedureDefinition.hospital_id == hospital_id,
            ImagingProcedureDefinition.code == payload.test_code,
            ImagingProcedureDefinition.status == "active",
        ))
    if test is None or test.name.casefold() != payload.test_name.casefold():
        raise HTTPException(status_code=422, detail={"code": "active_hospital_test_definition_required"})
    session_context = _authorized_session(db, user.id, hospital_id, case.session_id)
    _source_message(db, session_context, user.id, payload.source_sequence, payload.source_digest, payload.evidence_citation_ids)
    item = DiagnosticTestConsideration(
        hospital_id=hospital_id, case_id=case.id, test_code=payload.test_code,
        test_name=test.name, modality=payload.modality, priority=payload.priority,
        rationale=payload.rationale, source_sequence=payload.source_sequence,
        source_digest=payload.source_digest, evidence_citation_ids=payload.evidence_citation_ids,
        entered_by_user_id=user.id,
    )
    db.add(item)
    case.status = "under_review"
    db.flush()
    _audit(db, hospital_id, user.id, "diagnostic_support.test_consideration_added", "diagnostic_test_consideration", item.id)
    result = DiagnosticTestConsiderationRead.model_validate(item)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result


@router.get("/cases/{case_id}/differentials", response_model=list[DiagnosticDifferentialRead])
def list_diagnostic_differentials(case_id: UUID, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _case(db, hospital_id, user.id, case_id)
    return db.scalars(select(DiagnosticDifferential).where(
        DiagnosticDifferential.hospital_id == hospital_id,
        DiagnosticDifferential.case_id == case_id,
    ).order_by(DiagnosticDifferential.created_at)).all()


@router.get("/cases/{case_id}/test-considerations", response_model=list[DiagnosticTestConsiderationRead])
def list_diagnostic_test_considerations(case_id: UUID, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _case(db, hospital_id, user.id, case_id)
    return db.scalars(select(DiagnosticTestConsideration).where(
        DiagnosticTestConsideration.hospital_id == hospital_id,
        DiagnosticTestConsideration.case_id == case_id,
    ).order_by(DiagnosticTestConsideration.created_at)).all()


@router.post("/differentials/{item_id}/review", response_model=DiagnosticDifferentialRead)
def review_diagnostic_differential(item_id: UUID, payload: DiagnosticDifferentialReview, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    item = db.scalar(select(DiagnosticDifferential).where(
        DiagnosticDifferential.hospital_id == hospital_id,
        DiagnosticDifferential.id == item_id,
    ).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "diagnostic_differential_not_found"})
    case = _case(db, hospital_id, user.id, item.case_id, lock=True)
    if case.status == "closed" or item.status != "proposed":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_differential_not_reviewable"})
    item.status = payload.status
    item.review_note = payload.review_note
    item.reviewed_by_user_id = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "diagnostic_support.differential_reviewed", "diagnostic_differential", item.id)
    result = DiagnosticDifferentialRead.model_validate(item)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result


@router.post("/test-considerations/{item_id}/review", response_model=DiagnosticTestConsiderationRead)
def review_diagnostic_test_consideration(item_id: UUID, payload: DiagnosticTestConsiderationReview, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    item = db.scalar(select(DiagnosticTestConsideration).where(
        DiagnosticTestConsideration.hospital_id == hospital_id,
        DiagnosticTestConsideration.id == item_id,
    ).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "diagnostic_test_consideration_not_found"})
    case = _case(db, hospital_id, user.id, item.case_id, lock=True)
    if case.status == "closed" or item.status != "proposed":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_test_consideration_not_reviewable"})
    item.status = payload.status
    item.review_note = payload.review_note
    item.reviewed_by_user_id = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "diagnostic_support.test_consideration_reviewed", "diagnostic_test_consideration", item.id)
    result = DiagnosticTestConsiderationRead.model_validate(item)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result


@router.post("/cases/{case_id}/close", response_model=DiagnosticSupportCaseRead)
def close_diagnostic_support_case(case_id: UUID, payload: DiagnosticSupportCaseClose, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    case = _case(db, hospital_id, user.id, case_id, lock=True)
    if case.status == "closed":
        raise HTTPException(status_code=409, detail={"code": "diagnostic_support_case_already_closed"})
    pending_differential = db.scalar(select(DiagnosticDifferential.id).where(
        DiagnosticDifferential.hospital_id == hospital_id,
        DiagnosticDifferential.case_id == case.id,
        DiagnosticDifferential.status == "proposed",
    ).limit(1))
    pending_test = db.scalar(select(DiagnosticTestConsideration.id).where(
        DiagnosticTestConsideration.hospital_id == hospital_id,
        DiagnosticTestConsideration.case_id == case.id,
        DiagnosticTestConsideration.status == "proposed",
    ).limit(1))
    if pending_differential is not None or pending_test is not None:
        raise HTTPException(status_code=409, detail={"code": "all_diagnostic_suggestions_must_be_reviewed"})
    case.clinician_assessment = payload.clinician_assessment
    case.status = "closed"
    case.closed_by_user_id = user.id
    case.closed_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "diagnostic_support.case_closed", "diagnostic_support_case", case.id)
    result = DiagnosticSupportCaseRead.model_validate(case)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return result
