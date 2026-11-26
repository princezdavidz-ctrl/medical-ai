from datetime import datetime, timezone
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.contracts import AICapability
from app.ai.data_safety import contains_obvious_personal_identifiers
from app.ai.gateway import ModelUnavailable
from app.ai.orchestrator import KnowledgeUnavailable, UnsafeModelOutput
from app.ai.usage import AIUsageQuotaExceeded
from app.api.deps import get_current_patient_context
from app.api.routes.ai import get_ai_orchestrator
from app.core.config import get_settings
from app.db.session import get_db
from app.models import AIHospitalControl, AuditEvent, PatientConsent
from app.models.patient_portal import PatientPortalLink
from app.schemas.ai import AIResponseRead
from app.schemas.ai_patient import AIPatientAssistantRequest

router = APIRouter(prefix="/patient-portal/ai", tags=["AI patient assistant"])


def _audit(db: Session, *, user_id, hospital_id, action: str, outcome: str, reason: str,
           metadata: dict) -> None:
    db.add(AuditEvent(
        hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type="patient_ai_request", outcome=outcome, reason=reason,
        metadata_json=metadata,
    ))
    db.commit()


@router.post("/questions", response_model=AIResponseRead)
def ask_patient_assistant(
    payload: AIPatientAssistantRequest,
    request: Request,
    context=Depends(get_current_patient_context),
    db: Session = Depends(get_db),
):
    user, hospital_id = context
    settings = get_settings()
    metadata = {"capability": AICapability.MEDICAL_INFORMATION.value, "surface": "patient_portal"}

    if not settings.ai_requests_enabled:
        raise HTTPException(status_code=503, detail={"code": "ai_requests_disabled_by_safety_gate"})
    control = db.get(AIHospitalControl, hospital_id)
    if control is not None and control.ai_paused:
        raise HTTPException(status_code=503, detail={"code": "hospital_ai_execution_paused"})
    if contains_obvious_personal_identifiers(payload.question):
        raise HTTPException(status_code=422, detail={
            "code": "direct_identifiers_not_allowed",
            "message": "Please remove names, phone numbers, addresses, medical record numbers and other direct identifiers."
        })

    now = datetime.now(timezone.utc)
    link = db.scalar(select(PatientPortalLink).where(
        PatientPortalLink.hospital_id == hospital_id,
        PatientPortalLink.patient_id == payload.patient_id,
        PatientPortalLink.portal_user_id == user.id,
        PatientPortalLink.status == "active",
        or_(PatientPortalLink.expires_at.is_(None), PatientPortalLink.expires_at > now),
    ))
    if link is None or "ai_assistant" not in (link.access_scope or []):
        raise HTTPException(status_code=403, detail={"code": "verified_patient_portal_ai_scope_required"})

    consent = db.scalar(select(PatientConsent).where(
        PatientConsent.hospital_id == hospital_id,
        PatientConsent.patient_id == payload.patient_id,
        PatientConsent.purpose == "patient_ai_assistance",
        PatientConsent.status == "granted",
        PatientConsent.granted_at.is_not(None),
        PatientConsent.granted_at <= now,
        PatientConsent.expires_at.is_not(None),
        PatientConsent.expires_at > now,
        PatientConsent.withdrawn_at.is_(None),
    ))
    if consent is None or not isinstance(consent.scope, dict) or consent.scope.get("ai_processing") is not True:
        raise HTTPException(status_code=403, detail={"code": "active_patient_ai_consent_required"})

    gateway = getattr(request.app.state, "ai_gateway", None)
    orchestrator = get_ai_orchestrator(request, db)
    if gateway is None or not gateway.has_provider("local"):
        _audit(db, user_id=user.id, hospital_id=hospital_id, action="ai.patient.request.blocked",
               outcome="denied", reason="local_model_runtime_unavailable", metadata=metadata)
        raise HTTPException(status_code=503, detail={
            "code": "local_model_runtime_unavailable",
            "message": "The patient assistant is unavailable offline. No hosted provider or patient-data transfer was attempted."
        })

    prompt = (
        "Patient-facing health education request. Explain in plain, respectful language suitable for a general audience. "
        "Answer the question using only the approved evidence supplied to you. Do not diagnose, prescribe, change medication, "
        "interpret an individual test result, or make a personal treatment decision. If the user describes severe or rapidly "
        "worsening symptoms, advise immediate emergency assessment. For medication instructions, explain only general wording "
        "and tell the patient to follow the exact label and contact their pharmacist or treating clinician if unclear. "
        "For appointments, help prepare questions and a concise checklist. State uncertainty and when professional review is needed. "
        "Do not imply access to the patient's hospital record; this endpoint does not retrieve chart data.\n\n"
        "Patient question: " + payload.question.strip()
    )
    try:
        response = orchestrator.execute(
            capability=AICapability.MEDICAL_INFORMATION,
            prompt=prompt,
            hospital_id=hospital_id,
            actor_user_id=user.id,
            has_patient_context=True,
            patient_context=None,
        )
    except AIUsageQuotaExceeded as exc:
        raise HTTPException(status_code=429, detail={"code": str(exc) or "ai_usage_quota_exceeded"}) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"code": str(exc) or "ai_policy_denied"}) from exc
    except KnowledgeUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": "approved_medical_evidence_unavailable"}) from exc
    except UnsafeModelOutput as exc:
        raise HTTPException(status_code=502, detail={"code": "model_output_failed_evidence_validation"}) from exc
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": "local_model_runtime_unavailable"}) from exc

    digest = sha256(response.content.encode("utf-8")).hexdigest()
    citations = [{
        "citation_id": item.citation_id, "source_id": item.source_id,
        "source_title": item.source_title, "publisher": item.publisher,
        "canonical_url": item.canonical_url, "document_id": item.document_id,
        "title": item.title, "version": item.version, "jurisdiction": item.jurisdiction,
        "evidence_grade": item.evidence_grade, "reviewed_at": item.reviewed_at,
        "next_review_at": item.next_review_at,
    } for item in response.citations]
    _audit(db, user_id=user.id, hospital_id=hospital_id, action="ai.patient.request.completed",
           outcome="success", reason="Patient education response generated from approved evidence",
           metadata={**metadata, "consent_id": str(consent.id), "citation_count": len(citations),
                     "provider_class": "local", "prompt_version": response.prompt_version})
    return {
        "content": response.content, "provider": response.provider, "model": response.model,
        "model_version": response.model_version, "prompt_version": response.prompt_version,
        "prompt_digest": response.prompt_digest, "citations": citations,
        "clinical_use_enabled": False, "requires_clinician_review": True,
        "session_id": None, "assistant_sequence": None, "response_digest": digest,
    }
