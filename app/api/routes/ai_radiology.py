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
from app.models import (
    AISession, AISessionMessage, ClinicalAISessionContext,
    ImagingOrder, ImagingStudy, ImagingReport, ImagingProcedureDefinition,
)
from app.models.ai_radiology import AIRadiologyInterpretationCase
from app.schemas.ai_radiology import (
    AIRadiologyInterpretationCreate, AIRadiologyInterpretationRead,
    AIRadiologyInterpretationReview,
)

router = APIRouter(prefix="/ai/radiology", tags=["AI radiology assistant"])


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _patient_authorized(db: Session, *, user_id: UUID, hospital_id: UUID, patient_id: UUID, encounter_id: UUID, consent_id: UUID, assignment_id: UUID) -> None:
    try:
        authorized = load_authorized_patient_context(
            db, hospital_id=hospital_id, actor_user_id=user_id,
            patient_id=patient_id, encounter_id=encounter_id,
        )
    except PatientContextDenied as exc:
        raise HTTPException(status_code=403, detail={"code": str(exc)}) from exc
    if authorized.consent_id != consent_id or authorized.assignment_id != assignment_id:
        raise HTTPException(status_code=403, detail={"code": "radiology_case_authorization_context_changed"})


def _report_digest(report: ImagingReport) -> str:
    payload = {
        "id": str(report.id), "study_id": str(report.study_id),
        "findings": report.findings, "impression": report.impression,
        "status": report.status, "critical_flag": report.critical_flag,
        "critical_note": report.critical_note,
        "verified_by_user_id": str(report.verified_by_user_id) if report.verified_by_user_id else None,
        "verified_at": report.verified_at.isoformat() if report.verified_at else None,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _authorized_case(db: Session, *, user_id: UUID, hospital_id: UUID, case_id: UUID) -> AIRadiologyInterpretationCase:
    case = db.scalar(select(AIRadiologyInterpretationCase).where(
        AIRadiologyInterpretationCase.hospital_id == hospital_id,
        AIRadiologyInterpretationCase.id == case_id,
        AIRadiologyInterpretationCase.owner_user_id == user_id,
    ).with_for_update())
    if case is None:
        raise HTTPException(status_code=404, detail={"code": "radiology_interpretation_case_not_found"})
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
    if (
        session_context.patient_id != case.patient_id
        or session_context.encounter_id != case.encounter_id
        or session_context.consent_id != case.consent_id
        or session_context.assignment_id != case.assignment_id
    ):
        raise HTTPException(status_code=403, detail={"code": "radiology_session_context_mismatch"})
    _patient_authorized(
        db, user_id=user_id, hospital_id=hospital_id,
        patient_id=case.patient_id, encounter_id=case.encounter_id,
        consent_id=case.consent_id, assignment_id=case.assignment_id,
    )
    message = db.scalar(select(AISessionMessage).where(
        AISessionMessage.hospital_id == hospital_id,
        AISessionMessage.owner_user_id == user_id,
        AISessionMessage.session_id == case.session_id,
        AISessionMessage.sequence_number == case.source_assistant_sequence,
        AISessionMessage.role == "assistant",
    ))
    metadata = (message.metadata_json or {}) if message else {}
    if message is None or metadata.get("response_digest") != case.source_response_digest or metadata.get("capability") != AICapability.RADIOLOGY_SUPPORT.value:
        raise HTTPException(status_code=409, detail={"code": "radiology_source_response_mismatch"})
    report = db.scalar(select(ImagingReport).where(
        ImagingReport.hospital_id == hospital_id, ImagingReport.id == case.report_id,
    ))
    if report is None or _report_digest(report) != case.report_digest:
        case.status = "stale"
        db.commit()
        _restore_context(db, user_id, hospital_id)
        raise HTTPException(status_code=409, detail={"code": "source_radiology_report_changed_case_stale"})
    return case


@router.post("/interpretations", response_model=AIRadiologyInterpretationRead, status_code=status.HTTP_201_CREATED)
def create_radiology_interpretation(
    payload: AIRadiologyInterpretationCreate,
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
    _patient_authorized(
        db, user_id=user.id, hospital_id=hospital_id,
        patient_id=session_context.patient_id, encounter_id=session_context.encounter_id,
        consent_id=session_context.consent_id, assignment_id=session_context.assignment_id,
    )
    message = db.scalar(select(AISessionMessage).where(
        AISessionMessage.hospital_id == hospital_id, AISessionMessage.owner_user_id == user.id,
        AISessionMessage.session_id == payload.session_id,
        AISessionMessage.sequence_number == payload.assistant_sequence, AISessionMessage.role == "assistant",
    ))
    metadata = (message.metadata_json or {}) if message else {}
    if message is None or metadata.get("response_digest") != payload.response_digest or metadata.get("capability") != AICapability.RADIOLOGY_SUPPORT.value:
        raise HTTPException(status_code=409, detail={"code": "radiology_source_response_mismatch"})

    report = db.scalar(select(ImagingReport).where(
        ImagingReport.hospital_id == hospital_id, ImagingReport.id == payload.report_id,
        ImagingReport.status == "final",
        ImagingReport.verified_by_user_id.is_not(None),
        ImagingReport.verified_at.is_not(None),
    ))
    if report is None:
        raise HTTPException(status_code=422, detail={"code": "only_verified_final_imaging_reports_are_eligible"})
    study = db.scalar(select(ImagingStudy).where(
        ImagingStudy.hospital_id == hospital_id, ImagingStudy.id == report.study_id,
        ImagingStudy.status == "completed",
    ))
    if study is None:
        raise HTTPException(status_code=422, detail={"code": "completed_imaging_study_required"})
    order = db.scalar(select(ImagingOrder).where(
        ImagingOrder.hospital_id == hospital_id, ImagingOrder.id == study.order_id,
        ImagingOrder.patient_id == session_context.patient_id,
        ImagingOrder.encounter_id == session_context.encounter_id,
        ImagingOrder.status == "completed",
    ))
    if order is None:
        raise HTTPException(status_code=422, detail={"code": "imaging_order_patient_encounter_mismatch"})
    definition = db.scalar(select(ImagingProcedureDefinition).where(
        ImagingProcedureDefinition.hospital_id == hospital_id,
        ImagingProcedureDefinition.id == order.procedure_definition_id,
        ImagingProcedureDefinition.status == "active",
    ))
    if definition is None:
        raise HTTPException(status_code=422, detail={"code": "active_imaging_procedure_definition_required"})
    current_digest = _report_digest(report)
    if current_digest != payload.report_digest:
        raise HTTPException(status_code=409, detail={"code": "imaging_report_digest_mismatch"})
    snapshot = {
        "report_id": str(report.id), "study_id": str(study.id), "order_id": str(order.id),
        "accession_number": study.accession_number, "modality": definition.modality,
        "procedure_name": definition.name, "body_region": definition.body_region,
        "clinical_indication": order.clinical_indication, "priority": order.priority,
        "findings": report.findings, "impression": report.impression,
        "critical_flag": report.critical_flag, "critical_note": report.critical_note,
        "verified_by_user_id": str(report.verified_by_user_id),
        "verified_at": report.verified_at.isoformat(),
    }
    case = AIRadiologyInterpretationCase(
        hospital_id=hospital_id, session_id=payload.session_id, owner_user_id=user.id,
        patient_id=session_context.patient_id, encounter_id=session_context.encounter_id,
        consent_id=session_context.consent_id, assignment_id=session_context.assignment_id,
        order_id=order.id, study_id=study.id, report_id=report.id,
        report_digest=current_digest, report_snapshot=snapshot,
        source_assistant_sequence=payload.assistant_sequence, source_response_digest=payload.response_digest,
    )
    db.add(case)
    try:
        db.flush()
        write_audit_event(db, hospital_id=hospital_id, actor_user_id=user.id,
            action="ai.radiology_interpretation.created", resource_type="ai_radiology_interpretation_case",
            resource_id=str(case.id), metadata={"modality": definition.modality, "critical_flag": report.critical_flag})
        db.commit()
    except IntegrityError:
        db.rollback()
        _restore_context(db, user.id, hospital_id)
        raise HTTPException(status_code=409, detail={"code": "radiology_interpretation_already_exists_or_conflicts"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.get("/interpretations/{case_id}", response_model=AIRadiologyInterpretationRead)
def get_radiology_interpretation(case_id: UUID, context=Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    return _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)


@router.post("/interpretations/{case_id}/review", response_model=AIRadiologyInterpretationRead)
def review_radiology_interpretation(
    case_id: UUID, payload: AIRadiologyInterpretationReview,
    context=Depends(get_current_context), db: Session = Depends(get_db),
):
    user, hospital_id = context
    case = _authorized_case(db, user_id=user.id, hospital_id=hospital_id, case_id=case_id)
    if case.status != "pending_review":
        raise HTTPException(status_code=409, detail={"code": "radiology_interpretation_not_pending_review"})
    case.status = "reviewed"
    case.review_decision = payload.decision
    case.review_reference = payload.review_reference
    case.review_note_reference = payload.note_reference
    case.reviewed_by_user_id = user.id
    case.reviewed_at = datetime.now(timezone.utc)
    write_audit_event(db, hospital_id=hospital_id, actor_user_id=user.id,
        action="ai.radiology_interpretation.reviewed", resource_type="ai_radiology_interpretation_case",
        resource_id=str(case.id), metadata={"decision": payload.decision})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case
