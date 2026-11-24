from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InsurerCreate(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    insurer_type: str = Field(pattern="^(kenya_sha|private|employer|other)$")


class InsurerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    insurer_type: str
    status: str
    created_at: datetime


class CoverageCreate(BaseModel):
    patient_id: UUID
    insurer_definition_id: UUID
    member_number: str = Field(min_length=1, max_length=120)
    policy_number: str | None = Field(default=None, max_length=120)
    principal_member_name: str | None = Field(default=None, max_length=180)
    relationship_to_principal: str | None = Field(default=None, max_length=40)
    start_date: datetime
    end_date: datetime | None = None


class CoverageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    insurer_definition_id: UUID
    member_number: str
    policy_number: str | None
    start_date: datetime
    end_date: datetime | None
    status: str
    verification_reference: str | None
    verified_at: datetime | None


class ClaimCreate(BaseModel):
    patient_id: UUID
    encounter_id: UUID
    coverage_id: UUID
    invoice_id: UUID
    claim_number: str = Field(min_length=3, max_length=80)
    claimed_amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    currency: str = Field(default="KES", pattern="^[A-Z]{3}$")
    submission_note: str | None = None


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    encounter_id: UUID
    coverage_id: UUID
    invoice_id: UUID
    claim_number: str
    external_claim_reference: str | None
    currency: str
    claimed_amount: Decimal
    approved_amount: Decimal
    paid_amount: Decimal
    status: str
    submitted_at: datetime | None
    adjudicated_at: datetime | None
    created_at: datetime


class ClaimSubmit(BaseModel):
    external_claim_reference: str = Field(min_length=2, max_length=160)
    note: str | None = None


class ClaimAdjudicate(BaseModel):
    outcome: str = Field(pattern="^(accepted|partially_approved|rejected)$")
    approved_amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    note: str = Field(min_length=3)


class ClaimPayment(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    note: str | None = None
