from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClinicalAISessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    encounter_id: UUID


class ClinicalAISessionRead(BaseModel):
    session_id: UUID
    status: str
    expires_at: datetime
    clinical_use_enabled: Literal[False] = False


class ClinicalAISessionRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["user_requested", "consent_withdrawn", "assignment_changed", "security_concern"]


class AIClinicalReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assistant_sequence: int = Field(gt=0)
    response_digest: str = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
    decision: Literal["accepted_for_consideration", "rejected", "needs_revision"]
    feedback_category: Literal["helpful", "inaccurate", "missing_context", "unsafe", "unsupported", "needs_revision", "other"]
    correction_reference: str | None = Field(default=None, pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)
    note_reference: str | None = Field(default=None, pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class AIClinicalReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    session_id: UUID
    owner_user_id: UUID
    patient_id: UUID
    encounter_id: UUID
    assistant_sequence: int
    response_digest: str
    decision: str
    feedback_category: str | None
    correction_reference: str | None
    reviewed_by_user_id: UUID
    note_reference: str | None
    reviewed_at: datetime
