from dataclasses import replace
from uuid import UUID
from app.ai.contracts import (
    AICapability,
    AIModelRequest,
    AIModelResponse,
    KnowledgeRetriever,
    OperatingMode,
)
from app.ai.evidence import CitationValidationError, format_evidence_context, validate_response_citations
from app.ai.gateway import ModelGateway
from app.ai.policy import AIPolicyEngine


class KnowledgeUnavailable(RuntimeError):
    pass


class AIOrchestrator:
    """Coordinates policy, approved evidence retrieval and model execution."""

    def __init__(
        self, *, policy: AIPolicyEngine, gateway: ModelGateway, retriever: KnowledgeRetriever
    ) -> None:
        self.policy = policy
        self.gateway = gateway
        self.retriever = retriever

    def execute(
        self, *, capability: AICapability, prompt: str, hospital_id: UUID,
        actor_user_id: UUID, has_patient_context: bool = False,
    ) -> AIModelResponse:
        decision = self.policy.evaluate(
            capability=capability, has_patient_context=has_patient_context
        )
        if not decision.allowed or decision.provider_class is None:
            raise PermissionError(decision.reason_code)

        evidence = self.retriever.search(
            query=prompt, capability=capability, hospital_id=hospital_id
        )
        if not evidence:
            raise KnowledgeUnavailable("No approved, current medical evidence was retrieved")

        try:
            mode = OperatingMode(self.policy.settings.ai_operating_mode.lower())
        except ValueError:
            raise PermissionError("invalid_operating_mode") from None

        request = AIModelRequest(
            capability=capability,
            prompt=prompt,
            evidence=tuple(evidence),
            evidence_context=format_evidence_context(evidence),
            hospital_id=hospital_id,
            actor_user_id=actor_user_id,
            operating_mode=mode,
        )
        response = self.gateway.generate(
            provider_class=decision.provider_class,
            request=request,
        )
        try:
            citation_ids = validate_response_citations(response.content, evidence)
        except CitationValidationError as exc:
            raise PermissionError("model_response_failed_evidence_citation_validation") from exc
        evidence_by_id = {item.citation_id: item for item in evidence}
        citations = tuple(evidence_by_id[item] for item in citation_ids)
        return replace(response, citations=citations)
