from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ICUStayCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    admission_id: UUID
    admission_reason: str = Field(min_length=3, max_length=8000)

    @field_validator("admission_reason")
    @classmethod
    def normalize_admission_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("icu_admission_reason_too_short")
        return value


class ICUStayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    admission_id: UUID
    patient_id: UUID
    encounter_id: UUID
    bed_assignment_id: UUID
    ward_id: UUID
    department_id: UUID
    started_by_user_id: UUID
    status: str
    admission_reason: str
    started_at: datetime
    stepdown_requested_by_user_id: UUID | None
    stepdown_requested_at: datetime | None
    stepdown_reason: str | None
    closed_by_user_id: UUID | None
    closed_at: datetime | None


class ICUObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heart_rate: Decimal | None = Field(default=None, ge=1, le=300)
    respiratory_rate: Decimal | None = Field(default=None, ge=1, le=100)
    temperature_c: Decimal | None = Field(default=None, ge=25, le=45)
    systolic_bp: Decimal | None = Field(default=None, ge=30, le=300)
    diastolic_bp: Decimal | None = Field(default=None, ge=20, le=200)
    spo2_percent: Decimal | None = Field(default=None, ge=0, le=100)
    pain_score: int | None = Field(default=None, ge=0, le=10)
    gcs_eye: int | None = Field(default=None, ge=1, le=4)
    gcs_verbal: int | None = Field(default=None, ge=1, le=5)
    gcs_motor: int | None = Field(default=None, ge=1, le=6)
    oxygen_support: str | None = Field(default=None, max_length=120)
    ventilation_mode: str | None = Field(default=None, max_length=120)
    urine_output_ml: Decimal | None = Field(default=None, ge=0, le=100000)
    fluid_intake_ml: Decimal | None = Field(default=None, ge=0, le=100000)
    fluid_output_ml: Decimal | None = Field(default=None, ge=0, le=100000)
    notes: str | None = Field(default=None, max_length=8000)
    observed_at: datetime

    @model_validator(mode="after")
    def validate_observation(self):
        if self.systolic_bp is not None and self.diastolic_bp is not None:
            if self.systolic_bp <= self.diastolic_bp:
                raise ValueError("systolic_bp_must_exceed_diastolic_bp")
        values = (
            self.heart_rate, self.respiratory_rate, self.temperature_c,
            self.systolic_bp, self.diastolic_bp, self.spo2_percent,
            self.pain_score, self.gcs_eye, self.gcs_verbal, self.gcs_motor,
            self.oxygen_support, self.ventilation_mode,
            self.urine_output_ml, self.fluid_intake_ml, self.fluid_output_ml,
        )
        if not any(value is not None and (not isinstance(value, str) or value.strip()) for value in values):
            raise ValueError("icu_observation_requires_measurement")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("icu_observation_timestamp_must_include_timezone")
        if self.observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("icu_observation_timestamp_cannot_be_in_future")
        return self


class ICUObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recorded_by_user_id: UUID
    heart_rate: Decimal | None
    respiratory_rate: Decimal | None
    temperature_c: Decimal | None
    systolic_bp: Decimal | None
    diastolic_bp: Decimal | None
    spo2_percent: Decimal | None
    pain_score: int | None
    gcs_eye: int | None
    gcs_verbal: int | None
    gcs_motor: int | None
    oxygen_support: str | None
    ventilation_mode: str | None
    urine_output_ml: Decimal | None
    fluid_intake_ml: Decimal | None
    fluid_output_ml: Decimal | None
    notes: str | None
    observed_at: datetime
    recorded_at: datetime


class ICUCareEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal["assessment", "intervention", "procedure", "airway_support", "ventilation_change", "handover", "other"]
    description: str = Field(min_length=3, max_length=8000)
    performed_at: datetime

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("icu_care_event_description_too_short")
        return value

    @field_validator("performed_at")
    @classmethod
    def validate_performed_at(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("icu_event_timestamp_must_include_timezone")
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("icu_event_timestamp_cannot_be_in_future")
        return value


class ICUCareEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    performed_by_user_id: UUID
    event_type: str
    description: str
    performed_at: datetime
    recorded_at: datetime


class ICUProgressNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_type: Literal["daily_review", "progress", "handover", "incident", "other"]
    note_text: str = Field(min_length=3, max_length=16000)

    @field_validator("note_text")
    @classmethod
    def normalize_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("icu_progress_note_too_short")
        return value


class ICUProgressNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_user_id: UUID
    note_type: str
    note_text: str
    signed_at: datetime


class ICUStepdownRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=4000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("icu_stepdown_reason_too_short")
        return value


class ICUStayDetailRead(BaseModel):
    stay: ICUStayRead
    observations: list[ICUObservationRead]
    care_events: list[ICUCareEventRead]
    progress_notes: list[ICUProgressNoteRead]
