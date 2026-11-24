from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ImagingProcedureDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: UUID
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    modality: Literal[
        "xray", "ct", "mri", "ultrasound", "mammography",
        "fluoroscopy", "nuclear_medicine", "pet", "other",
    ]
    body_region: str = Field(min_length=2, max_length=120)
    contrast_policy: Literal["none", "optional", "required", "not_applicable"] = "not_applicable"
    preparation_instructions: str | None = Field(default=None, max_length=4000)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("imaging_procedure_code_required")
        return value

    @field_validator("name", "body_region")
    @classmethod
    def trim_required_catalog_text(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("imaging_catalog_text_required")
        return value

    @field_validator("preparation_instructions")
    @classmethod
    def trim_optional_instructions(cls, value):
        if value is not None:
            value = value.strip() or None
        return value


class ImagingProcedureDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    code: str
    name: str
    modality: str
    body_region: str
    contrast_policy: str
    preparation_instructions: str | None
    status: str
    created_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    retired_by_user_id: UUID | None
    retired_at: datetime | None
    retirement_reason: str | None
    created_at: datetime


class ImagingProcedureDefinitionRetire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("imaging_procedure_retirement_reason_required")
        return value


class ImagingOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    procedure_definition_id: UUID
    priority: Literal["routine", "urgent", "stat"] = "routine"
    clinical_indication: str = Field(min_length=3, max_length=4000)

    @field_validator("clinical_indication")
    @classmethod
    def trim_indication(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("imaging_clinical_indication_required")
        return value


class ImagingOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    ordering_department_id: UUID
    imaging_department_id: UUID
    procedure_definition_id: UUID
    ordered_by_user_id: UUID
    priority: str
    clinical_indication: str
    status: str
    ordered_at: datetime
    completed_at: datetime | None
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None


class ImagingStudyScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accession_number: str = Field(min_length=2, max_length=100)
    scheduled_at: datetime

    @field_validator("accession_number")
    @classmethod
    def normalize_accession(cls, value):
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("imaging_accession_number_required")
        return value

    @field_validator("scheduled_at")
    @classmethod
    def require_aware_schedule_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("imaging_schedule_timestamp_must_include_timezone")
        return value

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.scheduled_at < datetime.now(timezone.utc):
            raise ValueError("imaging_study_schedule_cannot_be_in_past")
        return self


class ImagingStudyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    accession_number: str
    scheduled_at: datetime
    performed_by_user_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    status: str
    pacs_system_reference: str | None
    pacs_study_uid: str | None


class ImagingStudyComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pacs_system_reference: str | None = Field(default=None, max_length=160)
    pacs_study_uid: str | None = Field(default=None, max_length=100)

    @field_validator("pacs_system_reference", "pacs_study_uid")
    @classmethod
    def trim_pacs_references(cls, value):
        if value is not None:
            value = value.strip() or None
        return value


class ImagingReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: str = Field(min_length=3, max_length=16000)
    impression: str = Field(min_length=3, max_length=8000)
    critical_flag: bool = False
    critical_note: str | None = Field(default=None, max_length=2000)

    @field_validator("findings", "impression", "critical_note")
    @classmethod
    def trim_report_text(cls, value):
        if value is not None:
            value = value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_report(self):
        if len(self.findings) < 3 or len(self.impression) < 3:
            raise ValueError("imaging_report_requires_findings_and_impression")
        if self.critical_flag and (self.critical_note is None or len(self.critical_note) < 3):
            raise ValueError("critical_imaging_finding_requires_escalation_note")
        if not self.critical_flag and self.critical_note is not None:
            raise ValueError("critical_note_requires_critical_flag")
        return self


class ImagingReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    study_id: UUID
    entered_by_user_id: UUID
    findings: str
    impression: str
    status: str
    critical_flag: bool
    critical_note: str | None
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    entered_at: datetime


class ImagingOrderCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("imaging_order_cancellation_reason_required")
        return value


class ImagingCriticalAcknowledgementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledgement_note: str = Field(min_length=3, max_length=2000)

    @field_validator("acknowledgement_note")
    @classmethod
    def trim_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("imaging_critical_acknowledgement_required")
        return value


class ImagingCriticalAcknowledgementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    report_id: UUID
    acknowledged_by_user_id: UUID
    acknowledgement_note: str
    acknowledged_at: datetime


class ImagingPatientSummary(BaseModel):
    medical_record_number: str
    given_name: str
    family_name: str


class ImagingOrderDetailRead(BaseModel):
    order: ImagingOrderRead
    patient: ImagingPatientSummary
    procedure: ImagingProcedureDefinitionRead
    study: ImagingStudyRead | None
    report: ImagingReportRead | None
    critical_acknowledgement: ImagingCriticalAcknowledgementRead | None
