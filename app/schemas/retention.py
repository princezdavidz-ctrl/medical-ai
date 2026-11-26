from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RetentionPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]+$")
    data_domain: Literal["clinical_records", "billing_records", "audit_logs", "communications", "security_logs", "hr_records", "other"]
    retention_days: int = Field(ge=1, le=36500)
    legal_basis: str = Field(min_length=10, max_length=4000)


class RetentionPolicyActivate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    effective_at: datetime

    @model_validator(mode="after")
    def validate_effective(self):
        if self.effective_at.tzinfo is None:
            raise ValueError("retention_effective_at_must_be_timezone_aware")
        return self


class RetentionPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    policy_code: str
    version: int
    data_domain: str
    retention_days: int
    legal_basis: str
    status: str
    effective_at: datetime | None
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    created_at: datetime


class LegalHoldCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hold_reference: str = Field(min_length=3, max_length=80)
    resource_references: list[str] = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=10, max_length=5000)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_hold(self):
        if any(not ref.startswith("vault://") for ref in self.resource_references):
            raise ValueError("legal_hold_resource_references_must_be_vault_refs")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("legal_hold_expiry_must_be_timezone_aware")
        return self


class LegalHoldRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")
    release_reason: str = Field(min_length=10, max_length=3000)


class LegalHoldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    hold_reference: str
    scope: dict
    reason: str
    issued_by_user_id: UUID
    issued_at: datetime
    expires_at: datetime | None
    status: str
    released_by_user_id: UUID | None
    released_at: datetime | None
    release_reason: str | None


class RetentionDispositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_id: UUID
    resource_type: str = Field(min_length=2, max_length=80)
    resource_reference: str = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)
    action: Literal["archive", "delete"]
    reason: str = Field(min_length=10, max_length=3000)
    resource_created_at: datetime

    @model_validator(mode="after")
    def validate_resource_date(self):
        if self.resource_created_at.tzinfo is None:
            raise ValueError("resource_created_at_must_be_timezone_aware")
        return self


class RetentionDispositionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    review_note: str = Field(min_length=10, max_length=3000)


class RetentionDispositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    policy_id: UUID
    resource_type: str
    resource_reference: str
    action: str
    reason: str
    eligible_at: datetime
    status: str
    requested_by_user_id: UUID
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
