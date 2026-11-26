from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ComplianceControlCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]+$")
    framework: Literal["kenya_dpa", "hipaa", "iso27001", "iso27799", "gdpr", "internal", "other"]
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=10, max_length=5000)
    owner_user_id: UUID
    evidence_requirements: list[str] = Field(default_factory=list, max_length=30)


class ComplianceControlRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    code: str
    version: int
    framework: str
    title: str
    description: str
    owner_user_id: UUID
    evidence_requirements: list[str]
    status: str
    created_by_user_id: UUID
    created_at: datetime


class ControlAssessmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: str = Field(min_length=10, max_length=5000)
    evidence_reference: str | None = Field(default=None, pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)
    next_review_at: datetime | None = None

    @model_validator(mode="after")
    def validate_next_review(self):
        if self.next_review_at is not None and self.next_review_at.tzinfo is None:
            raise ValueError("control_next_review_must_be_timezone_aware")
        return self


class ControlAssessmentReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["compliant", "partially_compliant", "non_compliant", "not_applicable"]


class ControlAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    control_id: UUID
    assessor_user_id: UUID
    status: str
    findings: str
    evidence_reference: str | None
    assessed_at: datetime
    next_review_at: datetime | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None


class AccessReviewCampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=180)
    period_start: datetime
    period_end: datetime
    due_at: datetime

    @model_validator(mode="after")
    def validate_period(self):
        if any(value.tzinfo is None for value in (self.period_start, self.period_end, self.due_at)):
            raise ValueError("access_review_dates_must_be_timezone_aware")
        if self.period_end <= self.period_start or self.due_at <= self.period_start:
            raise ValueError("access_review_period_or_due_date_invalid")
        return self


class AccessReviewCampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    title: str
    period_start: datetime
    period_end: datetime
    due_at: datetime
    status: str
    created_by_user_id: UUID
    completed_at: datetime | None
    created_at: datetime


class AccessReviewItemDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["keep", "change", "revoke"]
    justification: str = Field(min_length=10, max_length=3000)


class AccessReviewItemApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_note: str = Field(min_length=10, max_length=3000)


class AccessReviewItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    campaign_id: UUID
    subject_user_id: UUID
    role_name_snapshot: str
    department_id: UUID | None
    decision: str
    justification: str | None
    review_status: str
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    approval_note: str | None
    created_at: datetime
