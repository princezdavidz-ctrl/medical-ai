from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class AICapability(StrEnum):
    MEDICAL_INFORMATION = "medical_information"
    CLINICAL_DECISION_SUPPORT = "clinical_decision_support"
    LAB_INTERPRETATION = "lab_interpretation"
    MEDICATION_SAFETY = "medication_safety"
    RADIOLOGY_SUPPORT = "radiology_support"
    PATIENT_EDUCATION = "patient_education"
    HOSPITAL_OPERATIONS_ANALYTICS = "hospital_operations_analytics"
    VOICE_ASSISTANT = "voice_assistant"


class OperatingMode(StrEnum):
    HYBRID = "hybrid"
    OFFLINE = "offline"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class KnowledgeEvidence:
    citation_id: str
    document_id: str
    chunk_id: str
    source_id: str
    source_title: str
    publisher: str
    canonical_url: str | None
    title: str
    excerpt: str
    version: str
    jurisdiction: str
    evidence_grade: str | None
    reviewed_at: str
    next_review_at: str

    @property
    def citation_label(self) -> str:
        return f"[{self.citation_id}]"


@dataclass(frozen=True, slots=True)
class AIModelRequest:
    capability: AICapability
    prompt: str
    evidence: tuple[KnowledgeEvidence, ...]
    evidence_context: str
    hospital_id: UUID
    actor_user_id: UUID
    operating_mode: OperatingMode
    max_output_tokens: int = 1200
    prompt_version: str = "unregistered"
    prompt_digest: str = "unregistered"
    system_prompt: str = ""
    output_schema: dict[str, object] | None = None
    workflow_contract: dict[str, object] | None = None
    tool_permissions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AIModelResponse:
    content: str
    provider: str
    model: str
    model_version: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    usage_is_estimated: bool = True
    citations: tuple[KnowledgeEvidence, ...] = ()
    prompt_version: str = "unregistered"
    prompt_digest: str = "unregistered"


class AIProvider(Protocol):
    provider_id: str
    provider_class: str

    def generate(self, request: AIModelRequest) -> AIModelResponse: ...


class KnowledgeRetriever(Protocol):
    def search(
        self, *, query: str, capability: AICapability, hospital_id: UUID
    ) -> list[KnowledgeEvidence]: ...
