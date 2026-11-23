from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.ai.contracts import AICapability


class AIRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: AICapability
    prompt: str = Field(min_length=1, max_length=8000)
    patient_context_id: UUID | None = None
    encounter_id: UUID | None = None
    input_classification: Literal["public", "sensitive"] = "sensitive"
    session_id: UUID | None = None


class AICapabilityStatus(BaseModel):
    capability: AICapability
    approved: bool
    operating_mode: str
    status: str


class AICitationResponse(BaseModel):
    citation_id: str
    source_id: str
    source_title: str
    publisher: str
    canonical_url: str | None
    document_id: str
    title: str
    version: str
    jurisdiction: str
    evidence_grade: str | None
    reviewed_at: str
    next_review_at: str


class AIResponseRead(BaseModel):
    content: str
    provider: str
    model: str
    model_version: str
    prompt_version: str
    prompt_digest: str
    citations: list[AICitationResponse]
    clinical_use_enabled: Literal[False]
    requires_clinician_review: Literal[True]


class AIOperationsControlUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paused: bool
    reason: str = Field(min_length=3, max_length=500)
