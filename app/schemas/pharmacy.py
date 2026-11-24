from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


MedicationRoute = Literal[
    "oral", "topical", "inhalation", "intravenous", "intramuscular",
    "subcutaneous", "rectal", "ophthalmic", "otic", "nasal", "transdermal", "other",
]


class MedicationDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: UUID
    code: str = Field(min_length=2, max_length=80)
    generic_name: str = Field(min_length=2, max_length=180)
    brand_name: str | None = Field(default=None, max_length=180)
    active_ingredient: str = Field(min_length=2, max_length=180)
    strength_label: str = Field(min_length=1, max_length=100)
    dosage_form: str = Field(min_length=2, max_length=100)
    default_route: MedicationRoute | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("medication_code_required")
        return value

    @field_validator("generic_name", "active_ingredient", "strength_label", "dosage_form")
    @classmethod
    def trim_required_catalog_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("medication_catalog_text_required")
        return value

    @field_validator("brand_name")
    @classmethod
    def trim_brand_name(cls, value):
        if value is not None:
            value = value.strip() or None
        return value


class MedicationDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    code: str
    generic_name: str
    brand_name: str | None
    active_ingredient: str
    strength_label: str
    dosage_form: str
    default_route: str | None
    status: str
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    retired_by_user_id: UUID | None
    retired_at: datetime | None
    retirement_reason: str | None
    created_at: datetime


class MedicationDefinitionRetire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("medication_catalog_retirement_reason_required")
        return value


class MedicationOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medication_definition_id: UUID
    dose_text: str = Field(min_length=1, max_length=160)
    route: MedicationRoute
    frequency_text: str = Field(min_length=1, max_length=160)
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    quantity_prescribed: Decimal = Field(gt=0, le=1000000000)
    quantity_unit: str = Field(min_length=1, max_length=40)
    refills: int = Field(default=0, ge=0, le=12)
    indication: str = Field(min_length=3, max_length=4000)
    instructions: str | None = Field(default=None, max_length=4000)

    @field_validator("dose_text", "frequency_text", "quantity_unit", "indication")
    @classmethod
    def trim_required_order_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("medication_order_text_required")
        return value

    @field_validator("instructions")
    @classmethod
    def trim_optional_instructions(cls, value):
        if value is not None:
            value = value.strip() or None
        return value


class MedicationOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    ordering_department_id: UUID
    pharmacy_department_id: UUID
    medication_definition_id: UUID
    prescribed_by_user_id: UUID
    dose_text: str
    route: str
    frequency_text: str
    duration_days: int | None
    quantity_prescribed: Decimal
    quantity_unit: str
    refills: int
    indication: str
    instructions: str | None
    status: str
    quantity_dispensed_total: Decimal
    ordered_at: datetime
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None


class MedicationOrderReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "on_hold", "rejected"]
    review_note: str = Field(min_length=3, max_length=4000)

    @field_validator("review_note")
    @classmethod
    def trim_review_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("medication_review_note_required")
        return value


class MedicationOrderReviewEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    reviewed_by_user_id: UUID
    decision: str
    review_note: str
    reviewed_at: datetime


class MedicationDispenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity_dispensed: Decimal = Field(gt=0, le=1000000000)
    quantity_unit: str = Field(min_length=1, max_length=40)
    batch_reference: str | None = Field(default=None, max_length=120)
    dispense_note: str | None = Field(default=None, max_length=2000)

    @field_validator("quantity_unit")
    @classmethod
    def trim_quantity_unit(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("medication_dispense_unit_required")
        return value

    @field_validator("batch_reference", "dispense_note")
    @classmethod
    def trim_optional_dispense_text(cls, value):
        if value is not None:
            value = value.strip() or None
        return value


class MedicationDispenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    dispensed_by_user_id: UUID
    quantity_dispensed: Decimal
    quantity_unit: str
    batch_reference: str | None
    dispense_note: str | None
    dispensed_at: datetime


class MedicationOrderCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("medication_order_cancellation_reason_required")
        return value


class MedicationPatientSummary(BaseModel):
    medical_record_number: str
    given_name: str
    family_name: str


class MedicationOrderDetailRead(BaseModel):
    order: MedicationOrderRead
    patient: MedicationPatientSummary
    medication: MedicationDefinitionRead
    review_events: list[MedicationOrderReviewEventRead]
    dispenses: list[MedicationDispenseRead]


class MedicationQueueItemRead(BaseModel):
    order: MedicationOrderRead
    patient: MedicationPatientSummary
    medication: MedicationDefinitionRead
