from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.ai.contracts import AICapability
from app.ai.policy import AIPolicyEngine
from app.api.deps import get_current_context
from app.core.config import get_settings
from app.db.session import get_db
from app.models import AuditEvent
from app.schemas.ai import AIRequestCreate

router = APIRouter(prefix="/ai", tags=["central-medical-ai"])


@router.get("/capabilities", summary="List AI capabilities and their current availability")
def list_capabilities(
    context=Depends(get_current_context),
) -> dict:
    settings = get_settings()
    enabled = set(settings.ai_enabled_capabilities)
    mode = settings.ai_operating_mode.lower()
    statuses = []
    for capability in AICapability:
        approved = capability.value in enabled
        statuses.append({
            "capability": capability.value,
            "enabled": approved,
            "operating_mode": mode,
            "status": "not_configured",
        })
    return {"capabilities": statuses, "clinical_use_enabled": False}


@router.post("/requests", summary="Submit a request to the central Medical AI platform")
def submit_ai_request(
    payload: AIRequestCreate,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    settings = get_settings()
    policy = AIPolicyEngine(settings).evaluate(
        capability=payload.capability,
        has_patient_context=payload.patient_context_id is not None,
    )

    # The patient-context adapter and approved model/knowledge providers are
    # intentionally not wired yet. Never pass a patient identifier or prompt
    # to an external provider during this foundation milestone.
    if payload.patient_context_id is not None:
        reason = "patient_context_adapter_not_implemented"
    elif not policy.allowed:
        reason = policy.reason_code
    else:
        reason = "model_and_knowledge_runtime_not_configured"

    db.add(AuditEvent(
        hospital_id=hospital_id,
        actor_user_id=user.id,
        action="ai.request.blocked",
        resource_type="ai_request",
        resource_id=None,
        outcome="denied",
        reason=reason,
        metadata_json={"capability": payload.capability.value,
                       "operating_mode": settings.ai_operating_mode.lower()},
    ))
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": reason,
                "message": "The requested AI capability is not available yet. No clinical output was generated."},
    )
