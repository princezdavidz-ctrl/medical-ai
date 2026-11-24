from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PediatricCareRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: UUID


class PediatricCareRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    department_id: UUID
    created_by_user_id: UUID
    status: str
    created_at: datetime
    closed_at: datetime | None


class PediatricGrowthObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weight_kg: Decimal | None = Field(default=None, ge=0.2, le=300)
    height_cm: Decimal | None = Field(default=None, ge=20, le=250)
    head_circumference_cm: Decimal | None = Field(default=None, ge=10, le=100)
    mid_upper_arm_cm: Decimal | None = Field(default=None, ge=5, le=60)
    temperature_c: Decimal | None = Field(default=None, ge=25, le=45)
    source: Literal["measured", "reported"] = "measured"
    notes: str | None = Field(default=None, max_length=4000)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def require_aware_observation_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("pediatric_observation_timestamp_must_include_timezone")
        return value

    @model_validator(mode="after")
    def require_measurement(self):
        if all(value is None for value in (
            self.weight_kg, self.height_cm, self.head_circumference_cm,
            self.mid_upper_arm_cm, self.temperature_c,
        )):
            raise ValueError("pediatric_observation_requires_measurement")
        if self.observed_at > datetime.now(timezone.utc):
            raise ValueError("pediatric_observation_cannot_be_future_dated")
        return self


class PediatricGrowthObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recorded_by_user_id: UUID
    weight_kg: Decimal | None
    height_cm: Decimal | None
    head_circumference_cm: Decimal | None
    mid_upper_arm_cm: Decimal | None
    temperature_c: Decimal | None
    source: str
    notes: str | None
    observed_at: datetime
    recorded_at: datetime


class PediatricDevelopmentalScreeningCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_name: str = Field(min_length=2, max_length=160)
    instrument_version: str | None = Field(default=None, max_length=80)
    domain: Literal[
        "gross_motor", "fine_motor", "language", "cognitive",
        "social_emotional", "adaptive", "general",
    ]
    outcome: Literal[
        "age_appropriate", "monitor", "refer", "not_assessed", "unable_to_assess",
    ]
    referral_recommended: bool = False
    notes: str | None = Field(default=None, max_length=8000)
    screened_at: datetime

    @field_validator("instrument_name")
    @classmethod
    def trim_instrument_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("developmental_instrument_name_required")
        return value

    @field_validator("screened_at")
    @classmethod
    def require_aware_screening_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("developmental_screening_timestamp_must_include_timezone")
        return value

    @model_validator(mode="after")
    def validate_screening(self):
        if self.screened_at > datetime.now(timezone.utc):
            raise ValueError("developmental_screening_cannot_be_future_dated")
        if self.outcome == "refer" and not self.referral_recommended:
            raise ValueError("refer_outcome_requires_referral_recommendation")
        return self


class PediatricDevelopmentalScreeningRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recorded_by_user_id: UUID
    instrument_name: str
    instrument_version: str | None
    domain: str
    outcome: str
    referral_recommended: bool
    notes: str | None
    screened_at: datetime
    recorded_at: datetime


class PediatricImmunizationHistoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vaccine_label: str = Field(min_length=2, max_length=160)
    dose_label: str | None = Field(default=None, max_length=80)
    record_status: Literal["administered", "reported", "deferred", "declined", "unknown"]
    source: Literal["facility_record", "caregiver_report", "external_record"] = "facility_record"
    administered_at: datetime | None = None
    batch_reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("vaccine_label")
    @classmethod
    def trim_vaccine_label(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("vaccine_label_required")
        return value

    @field_validator("administered_at")
    @classmethod
    def require_aware_immunization_time(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("immunization_timestamp_must_include_timezone")
        return value

    @model_validator(mode="after")
    def validate_immunization_history(self):
        if self.record_status == "administered" and self.administered_at is None:
            raise ValueError("administered_immunization_requires_timestamp")
        if self.administered_at is not None and self.administered_at > datetime.now(timezone.utc):
            raise ValueError("immunization_timestamp_cannot_be_future_dated")
        if self.record_status == "administered" and self.source == "caregiver_report":
            raise ValueError("caregiver_report_must_not_claim_facility_administered_status")
        return self


class PediatricImmunizationHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recorded_by_user_id: UUID
    vaccine_label: str
    dose_label: str | None
    record_status: str
    source: str
    administered_at: datetime | None
    batch_reference: str | None
    notes: str | None
    recorded_at: datetime


class PediatricClinicalNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_type: Literal["assessment", "progress", "handover", "discharge", "other"]
    note_text: str = Field(min_length=3, max_length=12000)

    @field_validator("note_text")
    @classmethod
    def trim_note_text(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("pediatric_note_too_short")
        return value


class PediatricClinicalNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    authored_by_user_id: UUID
    note_type: str
    note_text: str
    signed_at: datetime


class PediatricCareRecordDetailRead(BaseModel):
    record: PediatricCareRecordRead
    growth_observations: list[PediatricGrowthObservationRead]
    developmental_screenings: list[PediatricDevelopmentalScreeningRead]
    immunization_history: list[PediatricImmunizationHistoryRead]
    notes: list[PediatricClinicalNoteRead]
