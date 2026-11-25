from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VendorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vendor_code: str = Field(min_length=2, max_length=80)
    legal_name: str = Field(min_length=2, max_length=240)
    vendor_type: str = Field(pattern="^(company|individual|nonprofit|government|other)$")
    registration_number: str | None = Field(default=None, max_length=120)
    tax_pin_reference: str | None = Field(default=None, max_length=120)
    contact_name: str | None = Field(default=None, max_length=180)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=40)

    @field_validator("vendor_code", "legal_name")
    @classmethod
    def trim_required(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("value_required")
        return value


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    vendor_code: str
    legal_name: str
    vendor_type: str
    registration_number: str | None
    status: str
    created_at: datetime


class RequisitionLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_description: str = Field(min_length=2, max_length=240)
    specification: str | None = Field(default=None, max_length=2000)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_of_measure: str = Field(min_length=1, max_length=40)
    estimated_unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    currency: str = Field(default="KES", pattern="^[A-Z]{3}$")


class RequisitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: UUID
    requisition_number: str = Field(min_length=3, max_length=80)
    purpose: str = Field(min_length=3, max_length=3000)
    required_by: datetime | None = None
    lines: list[RequisitionLineCreate] = Field(min_length=1, max_length=100)


class RequisitionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str = Field(pattern="^(approved|rejected)$")
    note: str = Field(min_length=3, max_length=2000)


class RequisitionLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    item_description: str
    specification: str | None
    quantity: Decimal
    unit_of_measure: str
    estimated_unit_cost: Decimal | None
    currency: str


class RequisitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    department_id: UUID
    requisition_number: str
    purpose: str
    required_by: datetime | None
    status: str
    requested_by_user_id: UUID
    submitted_at: datetime | None
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    decision_note: str | None
    created_at: datetime
    lines: list[RequisitionLineRead] = []


class PurchaseOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vendor_id: UUID
    order_number: str = Field(min_length=3, max_length=80)
    currency: str = Field(default="KES", pattern="^[A-Z]{3}$")
    unit_prices: dict[UUID, Decimal] = Field(min_length=1, max_length=100)


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    vendor_id: UUID
    requisition_id: UUID
    order_number: str
    currency: str
    total_amount: Decimal
    status: str
    created_by_user_id: UUID
    issued_by_user_id: UUID | None
    issued_at: datetime | None
    created_at: datetime


class PurchaseOrderIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, max_length=1000)
