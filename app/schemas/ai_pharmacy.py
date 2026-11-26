from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AIPharmacySafetyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    assistant_sequence: int = Field(gt=0)
    response_digest: str = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
    order_id: UUID
    order_digest: str = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)


class AIPharmacySafetyReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["accepted_for_pharmacist_consideration", "needs_correction", "not_applicable"]
    review_reference: str = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)
    note_reference: str | None = Field(default=None, pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class AIPharmacySafetyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    session_id: UUID
    owner_user_id: UUID
    patient_id: UUID
    encounter_id: UUID
    order_id: UUID
    order_digest: str
    order_snapshot: dict[str, Any]
    source_assistant_sequence: int
    source_response_digest: str
    status: str
    review_decision: str | None
    review_reference: str | None
    review_note_reference: str | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
