from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompliancePolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]+$")
    title: str = Field(min_length=3, max_length=180)
    document_reference: str = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class CompliancePolicyPublish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    effective_at: datetime

    @model_validator(mode="after")
    def validate_effective_at(self):
        if self.effective_at.tzinfo is None:
            raise ValueError("policy_effective_at_must_be_timezone_aware")
        return self


class CompliancePolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    policy_code: str
    version: int
    title: str
    document_reference: str
    status: str
    effective_at: datetime | None
    created_by_user_id: UUID
    published_by_user_id: UUID | None
    published_at: datetime | None
    created_at: datetime


class PolicyAcknowledgementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    policy_id: UUID
    user_id: UUID
    acknowledgement_method: str
    acknowledged_at: datetime


class SecurityIncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["data_breach", "unauthorized_access", "malware", "loss_or_theft", "service_disruption", "insider_threat", "phishing", "other"]
    affected_system: str | None = Field(default=None, max_length=180)
    summary: str = Field(min_length=10, max_length=5000)
    immediate_actions: str | None = Field(default=None, max_length=5000)


class SecurityIncidentTriage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity: Literal["low", "moderate", "high", "critical", "unclassified"]
    breach_assessment: Literal["pending", "confirmed", "not_confirmed", "not_required"]


class SecurityIncidentAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_to_user_id: UUID


class SecurityIncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["investigating", "contained", "resolved"]
    immediate_actions: str | None = Field(default=None, max_length=5000)


class SecurityIncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    reporter_user_id: UUID | None
    reporter_confidential: bool
    assigned_to_user_id: UUID | None
    category: str
    severity: str
    status: str
    breach_assessment: str
    affected_system: str | None
    summary: str
    immediate_actions: str | None
    reported_at: datetime
    contained_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ComplianceRiskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_user_id: UUID
    category: Literal["clinical", "privacy", "cybersecurity", "operational", "financial", "regulatory", "third_party", "other"]
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=10, max_length=5000)
    likelihood: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    mitigation_plan: str = Field(min_length=10, max_length=5000)
    due_at: datetime

    @model_validator(mode="after")
    def validate_due(self):
        if self.due_at.tzinfo is None:
            raise ValueError("risk_due_at_must_be_timezone_aware")
        return self


class ComplianceRiskReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    residual_likelihood: int = Field(ge=1, le=5)
    residual_impact: int = Field(ge=1, le=5)
    mitigation_plan: str = Field(min_length=10, max_length=5000)
    status: Literal["mitigating", "accepted", "closed"]


class ComplianceRiskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    owner_user_id: UUID
    category: str
    title: str
    description: str
    likelihood: int
    impact: int
    inherent_score: int
    residual_likelihood: int
    residual_impact: int
    residual_score: int
    mitigation_plan: str
    due_at: datetime
    status: str
    created_by_user_id: UUID
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
