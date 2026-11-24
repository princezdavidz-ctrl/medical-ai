from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EmergencyVisitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID
    department_id: UUID
    arrival_mode: Literal["walk_in", "ambulance", "referral", "police", "other"]
    chief_complaint: str = Field(min_length=3, max_length=4000)
    arrival_note: str | None = Field(default=None, max_length=1000)

    @field_validator("chief_complaint")
    @classmethod
    def normalize_chief_complaint(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("emergency_chief_complaint_too_short")
        return value


class EmergencyPatientSummary(BaseModel):
    id: UUID
    medical_record_number: str
    given_name: str
    preferred_name: str | None
    family_name: str
    date_of_birth: datetime | None = None
    administrative_sex: str | None


class EmergencyVisitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    department_id: UUID
    arrival_mode: str
    arrival_note: str | None
    status: str
    priority: str
    arrival_at: datetime
    triaged_at: datetime | None
    treatment_started_at: datetime | None
    completed_at: datetime | None
    assigned_clinician_user_id: UUID | None
    disposition: str | None
    disposition_note: str | None
    closed_at: datetime | None


class EmergencyTriageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triage_level: Literal["resuscitation", "emergent", "urgent", "less_urgent", "non_urgent"]
    chief_complaint: str = Field(min_length=3, max_length=4000)
    red_flag_present: bool = False
    red_flag_note: str | None = Field(default=None, max_length=2000)
    heart_rate: Decimal | None = Field(default=None, ge=1, le=300)
    respiratory_rate: Decimal | None = Field(default=None, ge=1, le=100)
    temperature_c: Decimal | None = Field(default=None, ge=25, le=45)
    systolic_bp: Decimal | None = Field(default=None, ge=30, le=300)
    diastolic_bp: Decimal | None = Field(default=None, ge=20, le=200)
    spo2_percent: Decimal | None = Field(default=None, ge=0, le=100)
    pain_score: int | None = Field(default=None, ge=0, le=10)
    consciousness_level: Literal["alert", "voice", "pain", "unresponsive", "not_assessed"] | None = None
    clinical_notes: str | None = Field(default=None, max_length=8000)

    @field_validator("chief_complaint")
    @classmethod
    def trim_triage_complaint(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("emergency_triage_complaint_too_short")
        return value

    @field_validator("red_flag_note")
    @classmethod
    def trim_red_flag_note(cls, value):
        if value is not None:
            value = value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_triage(self):
        if self.red_flag_present and (
            self.red_flag_note is None or len(self.red_flag_note) < 3
        ):
            raise ValueError("emergency_red_flag_requires_escalation_note")
        if self.red_flag_present and self.triage_level in {"less_urgent", "non_urgent"}:
            raise ValueError("emergency_red_flag_requires_urgent_triage_level")
        if self.systolic_bp is not None and self.diastolic_bp is not None:
            if self.systolic_bp <= self.diastolic_bp:
                raise ValueError("systolic_bp_must_exceed_diastolic_bp")
        return self


class EmergencyTriageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    revision: int
    triage_level: str
    chief_complaint: str
    red_flag_present: bool
    red_flag_note: str | None
    heart_rate: Decimal | None
    respiratory_rate: Decimal | None
    temperature_c: Decimal | None
    systolic_bp: Decimal | None
    diastolic_bp: Decimal | None
    spo2_percent: Decimal | None
    pain_score: int | None
    consciousness_level: str | None
    clinical_notes: str | None
    assessed_by_user_id: UUID
    assessed_at: datetime


class EmergencyCareEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal["assessment", "intervention", "procedure", "reassessment", "handover"]
    description: str = Field(min_length=3, max_length=8000)
    performed_at: datetime

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("emergency_event_description_too_short")
        return value

    @field_validator("performed_at")
    @classmethod
    def validate_performed_at(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("emergency_event_timestamp_must_include_timezone")
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("emergency_event_timestamp_cannot_be_in_future")
        return value


class EmergencyCareEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    performed_by_user_id: UUID
    event_type: str
    description: str
    performed_at: datetime
    recorded_at: datetime


class EmergencyNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_type: Literal["progress", "handover", "incident", "discharge", "other"]
    note_text: str = Field(min_length=3, max_length=16000)

    @field_validator("note_text")
    @classmethod
    def normalize_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("emergency_note_too_short")
        return value


class EmergencyNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_user_id: UUID
    note_type: str
    note_text: str
    signed_at: datetime


class EmergencyDispositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: Literal[
        "discharged", "admission_requested", "referred",
        "transfer_requested", "left_without_being_seen",
    ]
    note: str = Field(min_length=3, max_length=4000)

    @field_validator("note")
    @classmethod
    def normalize_disposition_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("emergency_disposition_note_too_short")
        return value


class EmergencyVisitDetailRead(BaseModel):
    visit: EmergencyVisitRead
    patient: EmergencyPatientSummary
    triage_history: list[EmergencyTriageRead]
    care_events: list[EmergencyCareEventRead]
    notes: list[EmergencyNoteRead]
