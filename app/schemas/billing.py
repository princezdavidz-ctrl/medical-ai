from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


CurrencyCode = str


class BillingServiceDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: UUID
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    unit_price: Decimal = Field(ge=0, le=999999999999.99, max_digits=14, decimal_places=2)
    currency: CurrencyCode = Field(default="KES", min_length=3, max_length=3)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("billing_service_code_required")
        return value

    @field_validator("name")
    @classmethod
    def trim_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("billing_service_name_required")
        return value

    @field_validator("description")
    @classmethod
    def trim_description(cls, value):
        if value is not None:
            value = value.strip() or None
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value):
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("billing_currency_must_be_three_letter_code")
        return value


class BillingServiceDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    code: str
    name: str
    description: str | None
    unit_price: Decimal
    currency: str
    status: str
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    retired_by_user_id: UUID | None
    retired_at: datetime | None
    retirement_reason: str | None
    created_at: datetime


class BillingServiceDefinitionRetire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("billing_service_retirement_reason_required")
        return value


class InvoiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: CurrencyCode = Field(default="KES", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value):
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("invoice_currency_must_be_three_letter_code")
        return value


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    department_id: UUID
    invoice_number: str
    currency: str
    subtotal_total: Decimal
    amount_paid_total: Decimal
    status: str
    created_by_user_id: UUID
    issued_by_user_id: UUID | None
    issued_at: datetime | None
    void_by_user_id: UUID | None
    void_at: datetime | None
    void_reason: str | None
    created_at: datetime


class InvoiceLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_definition_id: UUID
    quantity: Decimal = Field(gt=0, le=999999999.999, max_digits=12, decimal_places=3)


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    service_definition_id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    currency: str
    created_by_user_id: UUID
    created_at: datetime


class InvoiceVoid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("invoice_void_reason_required")
        return value


class InvoicePaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, le=99999999999999.99, max_digits=16, decimal_places=2)
    method: Literal["cash", "card", "bank_transfer", "mobile_money", "cheque", "other"]
    external_reference: str | None = Field(default=None, max_length=160)

    @field_validator("external_reference")
    @classmethod
    def trim_external_reference(cls, value):
        if value is not None:
            value = value.strip() or None
        return value


class InvoicePaymentFail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failure_note: str = Field(min_length=3, max_length=2000)

    @field_validator("failure_note")
    @classmethod
    def trim_failure_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("payment_failure_note_required")
        return value


class InvoicePaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    created_by_user_id: UUID
    amount: Decimal
    currency: str
    method: str
    external_reference: str | None
    status: str
    confirmed_by_user_id: UUID | None
    confirmed_at: datetime | None
    failure_note: str | None
    created_at: datetime


class BillingPatientSummary(BaseModel):
    medical_record_number: str
    given_name: str
    family_name: str


class InvoiceDetailRead(BaseModel):
    invoice: InvoiceRead
    patient: BillingPatientSummary
    lines: list[InvoiceLineRead]
    payments: list[InvoicePaymentRead]


class InvoiceQueueItemRead(BaseModel):
    invoice: InvoiceRead
    patient: BillingPatientSummary
