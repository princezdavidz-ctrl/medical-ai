from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticSupportCaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    problem_representation: str = Field(min_length=10, max_length=4000)
    known_findings: list[str] = Field(default_factory=list, max_length=50)
    missing_information: list[str] = Field(default_factory=list, max_length=50)
    red_flags: list[str] = Field(default_factory=list, max_length=30)


class DiagnosticSupportCaseClose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clinician_assessment: str = Field(min_length=20, max_length=5000)


class DiagnosticSupportCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    encounter_id: UUID
    session_id: UUID
    created_by_user_id: UUID
    problem_representation: str
    known_findings: list[str]
    missing_information: list[str]
    red_flags: list[str]
    status: str
    clinician_assessment: str | None
    closed_by_user_id: UUID | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DiagnosticDifferentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concept_code: str = Field(min_length=2, max_length=80)
    display_name: str = Field(min_length=2, max_length=180)
    rationale: str = Field(min_length=10, max_length=3000)
    source_sequence: int = Field(gt=0)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
    evidence_citation_ids: list[str] = Field(default_factory=list, max_length=30)


class DiagnosticTestConsiderationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_code: str = Field(min_length=2, max_length=80)
    test_name: str = Field(min_length=2, max_length=180)
    modality: Literal["laboratory", "imaging"]
    priority: Literal["routine", "urgent", "stat_consideration"] = "routine"
    rationale: str = Field(min_length=10, max_length=3000)
    source_sequence: int = Field(gt=0)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
    evidence_citation_ids: list[str] = Field(default_factory=list, max_length=30)


class DiagnosticDifferentialReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["considered", "ruled_out", "clinician_confirmed"]
    review_note: str = Field(min_length=10, max_length=3000)


class DiagnosticTestConsiderationReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["considered", "declined"]
    review_note: str = Field(min_length=10, max_length=3000)


class DiagnosticDifferentialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    case_id: UUID
    concept_code: str
    display_name: str
    rationale: str
    source_sequence: int
    source_digest: str
    evidence_citation_ids: list[str]
    status: str
    entered_by_user_id: UUID
    reviewed_by_user_id: UUID | None
    review_note: str | None
    reviewed_at: datetime | None
    created_at: object


class DiagnosticTestConsiderationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    case_id: UUID
    test_code: str
    test_name: str
    modality: str
    priority: str
    rationale: str
    source_sequence: int
    source_digest: str
    evidence_citation_ids: list[str]
    status: str
    entered_by_user_id: UUID
    reviewed_by_user_id: UUID | None
    review_note: str | None
    reviewed_at: object | None
    created_at: object
