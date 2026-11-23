from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.contracts import AICapability
from app.ai.data_safety import contains_obvious_personal_identifiers
from app.ai.gateway import ModelGateway, ModelUnavailable
from app.ai.orchestrator import AIOrchestrator, KnowledgeUnavailable, UnsafeModelOutput
from app.ai.patient_context import PatientContextDenied, load_authorized_patient_context
from app.ai.policy import AIPolicyEngine
from app.ai.session_crypto import SessionCipher, SessionEncryptionError
from app.ai.usage import AIUsageMeter, AIUsageQuotaExceeded
from app.ai.sessions import (
    AISessionUnavailable,
    append_ai_session_turn,
    create_ai_session,
    delete_owned_ai_session,
    list_owned_ai_sessions,
    read_owned_ai_session,
)
from app.api.deps import get_current_context
from app.core.config import get_settings
from app.db.session import get_db
from app.knowledge.retriever import SQLAlchemyKnowledgeRetriever
from app.models import AIUsageEvent, AuditEvent, HospitalMembership, Role
from app.schemas.ai import AIRequestCreate

router = APIRouter(prefix="/ai", tags=["central-medical-ai"])


def get_ai_orchestrator(request: Request, db: Session = Depends(get_db)) -> AIOrchestrator:
    settings = get_settings()
    gateway: ModelGateway = request.app.state.ai_gateway
    return AIOrchestrator(
        policy=AIPolicyEngine(settings),
        gateway=gateway,
        retriever=SQLAlchemyKnowledgeRetriever(db),
        usage_meter=AIUsageMeter(db=db, settings=settings),
    )


def _audit(
    db: Session, *, user_id, hospital_id, action: str,
    outcome: str, reason: str, metadata: dict,
    resource_type: str = "ai_request", resource_id: str | None = None,
) -> None:
    db.add(AuditEvent(
        hospital_id=hospital_id,
        actor_user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        reason=reason,
        metadata_json=metadata,
    ))
    db.commit()


@router.get("/capabilities", summary="List AI capabilities and their current availability")
def list_capabilities(
    request: Request,
    context=Depends(get_current_context),
) -> dict:
    settings = get_settings()
    gateway: ModelGateway | None = getattr(request.app.state, "ai_gateway", None)
    statuses = []
    policy = AIPolicyEngine(settings)
    for capability in AICapability:
        decision = policy.evaluate(capability=capability, has_patient_context=False)
        provider_configured = bool(
            decision.provider_class and gateway and gateway.has_provider(decision.provider_class)
        )
        if not settings.ai_requests_enabled:
            runtime_status = "disabled_by_safety_gate"
        elif capability.value not in settings.ai_enabled_capabilities:
            runtime_status = "capability_not_approved"
        elif not decision.allowed:
            runtime_status = decision.reason_code
        elif not provider_configured:
            runtime_status = "provider_not_configured"
        else:
            runtime_status = "configured_not_clinically_validated"
        statuses.append({
            "capability": capability.value,
            "approved": capability.value in settings.ai_enabled_capabilities,
            "operating_mode": settings.ai_operating_mode.lower(),
            "provider_configured": provider_configured,
            "status": runtime_status,
        })
    return {
        "requests_enabled": settings.ai_requests_enabled,
        "capabilities": statuses,
        "clinical_use_enabled": False,
    }


@router.post("/requests", summary="Submit a request to the central Medical AI platform")
def submit_ai_request(
    payload: AIRequestCreate,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
    orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> dict:
    user, hospital_id = context
    settings = get_settings()
    metadata = {"capability": payload.capability.value, "operating_mode": settings.ai_operating_mode.lower()}

    if not settings.ai_requests_enabled:
        reason = "ai_requests_disabled_by_safety_gate"
        _audit(db, user_id=user.id, hospital_id=hospital_id, action="ai.request.blocked",
               outcome="denied", reason=reason, metadata=metadata)
        raise HTTPException(status_code=503, detail={
            "code": reason, "message": "AI request execution is disabled. No clinical output was generated."
        })

    if payload.encounter_id is not None and payload.patient_context_id is None:
        raise HTTPException(status_code=422, detail={
            "code": "patient_id_required_for_encounter_context"
        })

    if contains_obvious_personal_identifiers(payload.prompt):
        reason = "direct_identifiers_not_allowed_in_free_text_prompt"
        _audit(
            db, user_id=user.id, hospital_id=hospital_id,
            action="ai.request.blocked", outcome="denied",
            reason=reason, metadata=metadata,
        )
        raise HTTPException(status_code=422, detail={
            "code": reason,
            "message": "Remove direct identifiers from the prompt. Use authorized structured patient context when needed."
        })

    if payload.patient_context_id is None and payload.input_classification != "public":
        reason = "sensitive_input_requires_authorized_patient_context"
        _audit(
            db, user_id=user.id, hospital_id=hospital_id,
            action="ai.request.blocked", outcome="denied",
            reason=reason, metadata=metadata,
        )
        raise HTTPException(status_code=403, detail={
            "code": reason,
            "message": "Sensitive or patient-specific requests must use an authorized patient context. Declare public only for non-identifiable general questions."
        })

    session_cipher = None
    conversation_history: list[dict[str, str]] = []
    if payload.session_id is not None:
        if not settings.ai_sessions_enabled:
            raise HTTPException(status_code=503, detail={"code": "ai_session_storage_disabled"})
        session_policy = AIPolicyEngine(settings).evaluate(
            capability=payload.capability, has_patient_context=True
        )
        if (
            not session_policy.allowed
            or session_policy.provider_class != "local"
            or not orchestrator.gateway.has_provider("local")
        ):
            reason = session_policy.reason_code if not session_policy.allowed else "session_requires_local_model"
            _audit(
                db, user_id=user.id, hospital_id=hospital_id,
                action="ai.session.blocked", outcome="denied",
                reason=reason, metadata={**metadata, "session_id": str(payload.session_id)},
                resource_type="ai_session", resource_id=str(payload.session_id),
            )
            raise HTTPException(status_code=503, detail={
                "code": reason,
                "message": "Conversation sessions require an approved local model. No hosted transfer was attempted."
            })
        session_cipher = _session_cipher(settings)
        try:
            session_record, previous_messages = read_owned_ai_session(
                db,
                hospital_id=hospital_id,
                owner_user_id=user.id,
                session_id=payload.session_id,
                cipher=session_cipher,
                max_messages=40,
                max_chars=20000,
            )
            conversation_history = [
                {"role": item["role"], "content": item["content"]}
                for item in previous_messages
            ]
            if (
                session_record.message_count > len(previous_messages)
                or any(item.get("content_truncated", False) for item in previous_messages)
            ):
                conversation_history.insert(0, {
                    "role": "context_notice",
                    "content": "Earlier conversation history was truncated; do not assume omitted details.",
                })
        except AISessionUnavailable as exc:
            raise HTTPException(status_code=404, detail={"code": str(exc)}) from exc
        except SessionEncryptionError as exc:
            raise HTTPException(status_code=503, detail={
                "code": "ai_session_content_unavailable",
                "message": "Conversation history could not be safely decrypted."
            }) from exc
        metadata = {**metadata, "session_id": str(payload.session_id)}

    patient_context = None
    if payload.patient_context_id is None and payload.session_id is None:
        route_decision = AIPolicyEngine(settings).evaluate(
            capability=payload.capability, has_patient_context=False
        )
        if route_decision.provider_class == "hosted":
            metadata = {**metadata, "input_classification": payload.input_classification}
            if payload.input_classification != "public":
                reason = "hosted_input_must_be_declared_public"
                _audit(
                    db, user_id=user.id, hospital_id=hospital_id,
                    action="ai.hosted_transfer.blocked", outcome="denied",
                    reason=reason, metadata=metadata,
                )
                raise HTTPException(status_code=403, detail={
                    "code": reason,
                    "message": "Hosted AI accepts only requests explicitly classified as public, non-patient information."
                })
            if not orchestrator.gateway.has_provider("hosted"):
                reason = "hosted_model_provider_not_configured"
                _audit(
                    db, user_id=user.id, hospital_id=hospital_id,
                    action="ai.hosted_transfer.blocked", outcome="denied",
                    reason=reason, metadata=metadata,
                )
                raise HTTPException(status_code=503, detail={
                    "code": reason, "message": "The explicitly approved hosted provider is unavailable."
                })
    if payload.patient_context_id is not None:
        preflight = AIPolicyEngine(settings).evaluate(
            capability=payload.capability, has_patient_context=True
        )
        if (
            not preflight.allowed
            or preflight.provider_class != "local"
            or not orchestrator.gateway.has_provider("local")
        ):
            reason = preflight.reason_code if not preflight.allowed else "local_model_provider_not_configured"
            _audit(
                db, user_id=user.id, hospital_id=hospital_id,
                action="ai.patient_context.blocked", outcome="denied",
                reason=reason, metadata={**metadata, "patient_context_requested": True},
                resource_type="patient_context", resource_id=str(payload.patient_context_id),
            )
            raise HTTPException(status_code=503, detail={
                "code": reason,
                "message": "Patient-context AI requires an approved, configured local model. No patient data was accessed."
            })
        try:
            authorized_context = load_authorized_patient_context(
                db,
                hospital_id=hospital_id,
                actor_user_id=user.id,
                patient_id=payload.patient_context_id,
                encounter_id=payload.encounter_id,
            )
            patient_context = authorized_context.patient_context
            metadata = {
                **metadata,
                "patient_context_requested": True,
                "patient_context_authorized": True,
                "encounter_id": str(authorized_context.encounter_id),
                "consent_id": str(authorized_context.consent_id),
                "assignment_id": str(authorized_context.assignment_id),
            }
        except PatientContextDenied as exc:
            reason = str(exc) or "patient_context_access_denied"
            _audit(
                db, user_id=user.id, hospital_id=hospital_id,
                action="ai.patient_context.denied", outcome="denied",
                reason=reason, metadata={**metadata, "patient_context_requested": True},
                resource_type="patient_context", resource_id=str(payload.patient_context_id),
            )
            raise HTTPException(status_code=403, detail={
                "code": reason, "message": "Patient context access was denied. No patient data was sent to a model."
            }) from exc

    try:
        response = orchestrator.execute(
            capability=payload.capability,
            prompt=payload.prompt,
            hospital_id=hospital_id,
            actor_user_id=user.id,
            has_patient_context=patient_context is not None or payload.session_id is not None,
            patient_context=patient_context,
            conversation_history=conversation_history,
        )
    except AIUsageQuotaExceeded as exc:
        reason = str(exc) or "ai_usage_quota_exceeded"
        _audit(
            db, user_id=user.id, hospital_id=hospital_id,
            action="ai.request.quota_blocked", outcome="denied",
            reason=reason, metadata=metadata,
        )
        status_code = 429 if reason.startswith("monthly_ai_") else 503
        raise HTTPException(status_code=status_code, detail={
            "code": reason,
            "message": "The hospital AI subscription quota or usage policy does not permit this request."
        }) from exc
    except PermissionError as exc:
        reason = str(exc) or "ai_policy_denied"
        _audit(db, user_id=user.id, hospital_id=hospital_id, action="ai.request.blocked",
               outcome="denied", reason=reason, metadata=metadata)
        raise HTTPException(status_code=403, detail={
            "code": reason, "message": "The request is not approved by current AI policy."
        }) from exc
    except KnowledgeUnavailable as exc:
        reason = "approved_medical_evidence_unavailable"
        _audit(db, user_id=user.id, hospital_id=hospital_id, action="ai.request.blocked",
               outcome="denied", reason=reason, metadata=metadata)
        raise HTTPException(status_code=503, detail={
            "code": reason, "message": "No approved, current evidence was found. No AI response was generated."
        }) from exc
    except UnsafeModelOutput as exc:
        reason = "model_output_failed_evidence_validation"
        _audit(db, user_id=user.id, hospital_id=hospital_id, action="ai.request.blocked",
               outcome="denied", reason=reason, metadata=metadata)
        raise HTTPException(status_code=502, detail={
            "code": reason, "message": "The model response failed evidence-citation validation and was withheld."
        }) from exc
    except ModelUnavailable as exc:
        reason = "approved_model_runtime_unavailable"
        _audit(db, user_id=user.id, hospital_id=hospital_id, action="ai.request.blocked",
               outcome="denied", reason=reason, metadata=metadata)
        raise HTTPException(status_code=503, detail={
            "code": reason, "message": "The approved model runtime is unavailable. No fallback was attempted."
        }) from exc

    if payload.session_id is not None and session_cipher is not None:
        try:
            append_ai_session_turn(
                db,
                hospital_id=hospital_id,
                owner_user_id=user.id,
                session_id=payload.session_id,
                user_prompt=payload.prompt,
                assistant_response=response.content,
                cipher=session_cipher,
                assistant_metadata={
                    "provider": response.provider,
                    "model": response.model,
                    "model_version": response.model_version,
                    "prompt_version": response.prompt_version,
                    "citation_ids": [item.citation_id for item in response.citations],
                    "requires_clinician_review": True,
                },
            )
        except (AISessionUnavailable, SessionEncryptionError) as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail={
                "code": "ai_session_persistence_failed",
                "message": "The response could not be securely persisted to the requested session."
            }) from exc

    _audit(
        db, user_id=user.id, hospital_id=hospital_id,
        action="ai.request.completed", outcome="success",
        reason="Evidence-grounded response generated",
        metadata={
            **metadata,
            "provider": response.provider,
            "model": response.model,
            "model_version": response.model_version,
            "prompt_version": response.prompt_version,
            "citation_count": len(response.citations),
        },
    )
    return {
        "content": response.content,
        "provider": response.provider,
        "model": response.model,
        "model_version": response.model_version,
        "prompt_version": response.prompt_version,
        "citations": [{
            "citation_id": item.citation_id,
            "source_id": item.source_id,
            "source_title": item.source_title,
            "publisher": item.publisher,
            "canonical_url": item.canonical_url,
            "document_id": item.document_id,
            "title": item.title,
            "version": item.version,
            "jurisdiction": item.jurisdiction,
            "evidence_grade": item.evidence_grade,
            "reviewed_at": item.reviewed_at,
            "next_review_at": item.next_review_at,
        } for item in response.citations],
        "clinical_use_enabled": False,
        "requires_clinician_review": True,
    }


def _session_cipher(settings) -> SessionCipher:
    if not settings.ai_sessions_enabled or settings.ai_session_encryption_keys is None:
        raise HTTPException(status_code=503, detail={
            "code": "ai_session_storage_disabled"
        })
    return SessionCipher.from_secret(
        keyring_secret=settings.ai_session_encryption_keys.get_secret_value(),
        active_key_version=settings.ai_session_active_key_version,
    )


@router.post("/sessions", summary="Create a private encrypted AI conversation session")
def create_session(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    settings = get_settings()
    _session_cipher(settings)
    session = create_ai_session(
        db,
        hospital_id=hospital_id,
        owner_user_id=user.id,
        retention_days=settings.ai_session_retention_days,
    )
    session_id_value = str(session.id)
    session_status = session.status
    session_message_count = session.message_count
    session_created_at = session.created_at
    session_expires_at = session.expires_at
    _audit(
        db, user_id=user.id, hospital_id=hospital_id,
        action="ai.session.created", outcome="success",
        reason="Encrypted AI session created",
        metadata={"session_id": session_id_value},
        resource_type="ai_session", resource_id=session_id_value,
    )
    return {
        "id": session_id_value,
        "status": session_status,
        "message_count": session_message_count,
        "created_at": session_created_at,
        "expires_at": session_expires_at,
    }


@router.get("/sessions", summary="List the current staff user's AI sessions")
def list_sessions(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    settings = get_settings()
    _session_cipher(settings)
    sessions = list_owned_ai_sessions(
        db, hospital_id=hospital_id, owner_user_id=user.id
    )
    return {
        "sessions": [{
            "id": str(item.id),
            "status": item.status,
            "message_count": item.message_count,
            "created_at": item.created_at,
            "last_message_at": item.last_message_at,
            "expires_at": item.expires_at,
        } for item in sessions]
    }


@router.get("/sessions/{session_id}", summary="Read an owned encrypted AI conversation")
def read_session(
    session_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    cipher = _session_cipher(get_settings())
    try:
        session, messages = read_owned_ai_session(
            db,
            hospital_id=hospital_id,
            owner_user_id=user.id,
            session_id=session_id,
            cipher=cipher,
        )
    except AISessionUnavailable as exc:
        raise HTTPException(status_code=404, detail={"code": str(exc)}) from exc
    except SessionEncryptionError as exc:
        raise HTTPException(status_code=503, detail={
            "code": "ai_session_content_unavailable",
            "message": "Encrypted session content could not be safely decrypted."
        }) from exc
    session_id_value = str(session.id)
    session_message_count = session.message_count
    session_expires_at = session.expires_at
    history_truncated = (
        session_message_count > len(messages)
        or any(item.get("content_truncated", False) for item in messages)
    )
    _audit(
        db, user_id=user.id, hospital_id=hospital_id,
        action="ai.session.read", outcome="success",
        reason="Owned encrypted AI session read",
        metadata={"session_id": session_id_value, "message_count": len(messages)},
        resource_type="ai_session", resource_id=session_id_value,
    )
    return {
        "id": session_id_value,
        "message_count": session_message_count,
        "expires_at": session_expires_at,
        "history_truncated": history_truncated,
        "messages": messages,
    }


@router.delete("/sessions/{session_id}", summary="Delete an owned AI session and its encrypted messages")
def delete_session(
    session_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    _session_cipher(get_settings())
    try:
        delete_owned_ai_session(
            db,
            hospital_id=hospital_id,
            owner_user_id=user.id,
            session_id=session_id,
        )
    except AISessionUnavailable as exc:
        raise HTTPException(status_code=404, detail={"code": str(exc)}) from exc
    _audit(
        db, user_id=user.id, hospital_id=hospital_id,
        action="ai.session.deleted", outcome="success",
        reason="Encrypted AI session content deleted",
        metadata={"session_id": str(session_id)},
        resource_type="ai_session", resource_id=str(session_id),
    )
    return {"id": str(session_id), "status": "deleted"}


@router.get("/usage", summary="View this hospital's AI subscription usage")
def get_ai_usage(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    membership = db.scalar(
        select(HospitalMembership)
        .join(Role, Role.id == HospitalMembership.role_id)
        .where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == user.id,
            HospitalMembership.status == "active",
        )
    )
    role = db.get(Role, membership.role_id) if membership else None
    role_name = role.name.strip().casefold().replace(" ", "_") if role else ""
    if role_name not in {"hospital_admin", "hospital_director", "finance_manager", "system_admin"}:
        raise HTTPException(status_code=403, detail={"code": "ai_usage_admin_role_required"})
    meter = AIUsageMeter(db=db, settings=get_settings())
    try:
        snapshot = meter.current_snapshot(hospital_id=hospital_id)
    except AIUsageQuotaExceeded as exc:
        raise HTTPException(status_code=503, detail={"code": str(exc)}) from exc
    events = db.scalars(
        select(AIUsageEvent)
        .where(AIUsageEvent.hospital_id == hospital_id)
        .order_by(AIUsageEvent.created_at.desc())
        .limit(100)
    ).all()
    event_data = [{
        "capability": item.capability,
        "operating_mode": item.operating_mode,
        "provider": item.provider_id,
        "model": item.model_id,
        "model_version": item.model_version,
        "input_tokens": item.input_tokens,
        "output_tokens": item.output_tokens,
        "cost_micros": item.cost_micros,
        "currency": item.currency,
        "latency_ms": item.latency_ms,
        "usage_is_estimated": item.usage_is_estimated,
        "outcome": item.outcome,
        "created_at": item.created_at,
    } for item in events]
    _audit(
        db, user_id=user.id, hospital_id=hospital_id,
        action="ai.usage.viewed", outcome="success",
        reason="Hospital AI usage dashboard viewed",
        metadata={"event_count": len(event_data), "policy_configured": snapshot.get("configured", False)},
        resource_type="ai_usage", resource_id=str(hospital_id),
    )
    return {
        "usage": snapshot,
        "recent_events": event_data,
    }
