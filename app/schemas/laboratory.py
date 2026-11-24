from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LaboratoryTestDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: UUID
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    specimen_type: str = Field(min_length=2, max_length=100)
    method: str | None = Field(default=None, max_length=160)
    result_unit: str | None = Field(default=None, max_length=80)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("laboratory_test_code_required")
        return value

    @field_validator("name", "specimen_type")
    @classmethod
    def trim_required_catalog_text(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("laboratory_catalog_text_required")
        return value


class LaboratoryTestDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    code: str
    name: str
    specimen_type: str
    method: str | None
    result_unit: str | None
    status: str
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    created_at: datetime


class LaboratoryOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_definition_id: UUID
    priority: Literal["routine", "urgent", "stat"] = "routine"
    clinical_indication: str = Field(min_length=3, max_length=4000)

    @field_validator("clinical_indication")
    @classmethod
    def trim_clinical_indication(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("laboratory_clinical_indication_required")
        return value


class LaboratoryOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    ordering_department_id: UUID
    laboratory_department_id: UUID
    test_definition_id: UUID
    ordered_by_user_id: UUID
    priority: str
    clinical_indication: str
    status: str
    ordered_at: datetime
    completed_at: datetime | None
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None


class LaboratorySpecimenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accession_number: str = Field(min_length=2, max_length=100)
    collected_at: datetime
    collection_status: Literal["collected", "rejected"] = "collected"
    rejection_reason: str | None = Field(default=None, max_length=2000)

    @field_validator("accession_number")
    @classmethod
    def normalize_accession(cls, value):
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("laboratory_accession_number_required")
        return value

    @field_validator("collected_at")
    @classmethod
    def require_aware_collection_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("laboratory_collection_timestamp_must_include_timezone")
        return value

    @field_validator("rejection_reason")
    @classmethod
    def trim_rejection_reason(cls, value):
        if value is not None:
            value = value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_collection(self):
        if self.collected_at > datetime.now(timezone.utc):
            raise ValueError("laboratory_collection_cannot_be_future_dated")
        if self.collection_status == "rejected" and (
            self.rejection_reason is None or len(self.rejection_reason) < 3
        ):
            raise ValueError("rejected_specimen_requires_reason")
        if self.collection_status == "collected" and self.rejection_reason is not None:
            raise ValueError("accepted_specimen_must_not_have_rejection_reason")
        return self


class LaboratorySpecimenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    accession_number: str
    specimen_type: str
    collected_by_user_id: UUID
    collected_at: datetime
    status: str
    received_at: datetime | None
    processing_started_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None


class LaboratoryResultCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_text: str | None = Field(default=None, max_length=12000)
    value_numeric: Decimal | None = Field(default=None, ge=-1000000000, le=1000000000)
    unit: str | None = Field(default=None, max_length=80)
    abnormality: Literal["not_flagged", "low", "high", "critical", "not_applicable"] = "not_flagged"
    interpretation_note: str | None = Field(default=None, max_length=8000)
    critical_flag: bool = False
    critical_note: str | None = Field(default=None, max_length=2000)

    @field_validator("value_text", "unit", "interpretation_note", "critical_note")
    @classmethod
    def trim_optional_result_text(cls, value):
        if value is not None:
            value = value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_result(self):
        if (self.value_text is None) == (self.value_numeric is None):
            raise ValueError("laboratory_result_requires_exactly_one_value")
        if self.value_numeric is not None and self.unit is None:
            raise ValueError("numeric_laboratory_result_requires_unit")
        if self.abnormality == "critical" and not self.critical_flag:
            raise ValueError("critical_abnormality_requires_critical_flag")
        if self.critical_flag and (
            self.critical_note is None or len(self.critical_note) < 3
        ):
            raise ValueError("critical_result_requires_manual_escalation_note")
        if not self.critical_flag and self.critical_note is not None:
            raise ValueError("critical_note_requires_critical_flag")
        return self


class LaboratoryResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    specimen_id: UUID
    entered_by_user_id: UUID
    value_text: str | None
    value_numeric: Decimal | None
    unit: str | None
    abnormality: str
    interpretation_note: str | None
    critical_flag: bool
    critical_note: str | None
    status: str
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    entered_at: datetime


class LaboratoryOrderCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("laboratory_cancellation_reason_required")
        return value


class LaboratoryCriticalAcknowledgementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledgement_note: str = Field(min_length=3, max_length=2000)

    @field_validator("acknowledgement_note")
    @classmethod
    def trim_acknowledgement_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("critical_result_acknowledgement_required")
        return value


class LaboratoryCriticalAcknowledgementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    result_id: UUID
    acknowledged_by_user_id: UUID
    acknowledgement_note: str
    acknowledged_at: datetime


class LaboratoryPatientSummary(BaseModel):
    medical_record_number: str
    given_name: str
    family_name: str


class LaboratoryOrderDetailRead(BaseModel):
    order: LaboratoryOrderRead
    patient: LaboratoryPatientSummary
    test: LaboratoryTestDefinitionRead
    specimens: list[LaboratorySpecimenRead]
    results: list[LaboratoryResultRead]
    critical_acknowledgement: LaboratoryCriticalAcknowledgementRead | None


class LaboratoryQueueItemRead(BaseModel):
    order: LaboratoryOrderRead
    patient: LaboratoryPatientSummary
    test: LaboratoryTestDefinitionRead


class LaboratorySpecimenReject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("laboratory_specimen_rejection_reason_required")
        return value
