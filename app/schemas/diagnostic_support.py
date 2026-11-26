from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


VaultReference = str


class DiagnosticSupportCaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    assistant_sequence: int = Field(gt=0)
    response_digest: str = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)


class DiagnosticSupportCaseClose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    closure_reference: VaultReference = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class DiagnosticSupportCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    session_id: UUID
    owner_user_id: UUID
    patient_id: UUID
    encounter_id: UUID
    source_assistant_sequence: int
    source_response_digest: str
    status: str
    closure_reference: str | None
    closed_by_user_id: UUID | None
    closed_at: datetime | None
    created_at: datetime


class DifferentialSuggestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: UUID
    concept_id: UUID
    concept_code: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=2, max_length=240)
    evidence_citation_ids: list[str] = Field(min_length=1, max_length=20)


class DifferentialSuggestionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["considered", "ruled_out", "clinician_confirmed"]
    review_reference: str | None = Field(default=None, pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class DifferentialSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    case_id: UUID
    document_id: UUID
    concept_id: UUID
    concept_code: str
    display_name: str
    evidence_citation_ids: list[str]
    status: str
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    review_reference: str | None
    created_at: datetime


class DiagnosticTestConsiderationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_domain: Literal["laboratory", "imaging"]
    laboratory_test_definition_id: UUID | None = None
    imaging_procedure_definition_id: UUID | None = None
    test_code: str = Field(min_length=2, max_length=80)
    test_name: str = Field(min_length=2, max_length=180)
    evidence_citation_ids: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_definition_pair(self):
        if self.test_domain == "laboratory":
            valid = self.laboratory_test_definition_id is not None and self.imaging_procedure_definition_id is None
        else:
            valid = self.imaging_procedure_definition_id is not None and self.laboratory_test_definition_id is None
        if not valid:
            raise ValueError("test_definition_must_match_domain")
        return self


class DiagnosticTestConsiderationReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["considered", "declined"]
    review_reference: str | None = Field(default=None, pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class DiagnosticTestConsiderationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    case_id: UUID
    test_domain: str
    laboratory_test_definition_id: UUID | None
    imaging_procedure_definition_id: UUID | None
    test_code: str
    test_name: str
    evidence_citation_ids: list[str]
    status: str
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    review_reference: str | None
    created_at: datetime
