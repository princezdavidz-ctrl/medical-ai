from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AILaboratoryInterpretationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    assistant_sequence: int = Field(gt=0)
    response_digest: str = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
    laboratory_result_ids: list[UUID] = Field(min_length=1, max_length=50)

    @field_validator("laboratory_result_ids")
    @classmethod
    def unique_result_ids(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("duplicate_laboratory_result_ids_not_allowed")
        return value


class AILaboratoryInterpretationReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["accepted_for_clinical_consideration", "needs_correction", "not_applicable"]
    review_reference: str = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)
    note_reference: str | None = Field(default=None, pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class AILaboratoryInterpretationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    session_id: UUID
    owner_user_id: UUID
    patient_id: UUID
    encounter_id: UUID
    source_assistant_sequence: int
    source_response_digest: str
    laboratory_result_ids: list[str]
    result_snapshot: list[dict[str, Any]]
    evidence_citation_ids: list[str]
    status: str
    review_decision: str | None
    review_note_reference: str | None
    review_reference: str | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
