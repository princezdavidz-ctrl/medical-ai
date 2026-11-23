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


class OperatingMode(StrEnum):
    HYBRID = "hybrid"
    OFFLINE = "offline"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class KnowledgeEvidence:
    source_id: str
    title: str
    excerpt: str
    version: str
    jurisdiction: str


@dataclass(frozen=True, slots=True)
class AIModelRequest:
    capability: AICapability
    prompt: str
    evidence: tuple[KnowledgeEvidence, ...]
    hospital_id: UUID
    actor_user_id: UUID
    operating_mode: OperatingMode


@dataclass(frozen=True, slots=True)
class AIModelResponse:
    content: str
    provider: str
    model: str
    model_version: str


class AIProvider(Protocol):
    provider_id: str
    provider_class: str

    def generate(self, request: AIModelRequest) -> AIModelResponse: ...


class KnowledgeRetriever(Protocol):
    def search(
        self, *, query: str, capability: AICapability, hospital_id: UUID
    ) -> list[KnowledgeEvidence]: ...
