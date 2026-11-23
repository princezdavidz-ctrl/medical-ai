from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OPDVisitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID
    department_id: UUID
    visit_type: Literal["walk_in", "appointment", "referral", "transfer"] = "walk_in"
    chief_complaint: str = Field(min_length=3, max_length=4000)
    assigned_clinician_user_id: UUID | None = None

    @field_validator("chief_complaint")
    @classmethod
    def trim_visit_complaint(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("opd_chief_complaint_too_short")
        return value


class OPDVisitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    department_id: UUID
    visit_date: date
    queue_token: str
    visit_type: str
    status: str
    priority: str
    arrival_at: datetime | None
    triage_at: datetime | None
    consultation_started_at: datetime | None
    completed_at: datetime | None
    assigned_clinician_user_id: UUID | None
    disposition: str | None
    disposition_note: str | None
    closed_at: datetime | None


class OPDTriageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triage_level: Literal["emergency", "very_urgent", "urgent", "standard", "non_urgent"]
    chief_complaint: str = Field(min_length=3, max_length=4000)
    red_flag_present: bool = False
    red_flag_note: str | None = Field(default=None, max_length=2000)
    heart_rate: Decimal | None = Field(default=None, ge=1, le=300)
    respiratory_rate: Decimal | None = Field(default=None, ge=1, le=100)
    temperature_c: Decimal | None = Field(default=None, ge=25, le=45)
    systolic_bp: Decimal | None = Field(default=None, ge=30, le=300)
    diastolic_bp: Decimal | None = Field(default=None, ge=20, le=200)
    spo2_percent: Decimal | None = Field(default=None, ge=0, le=100)
    weight_kg: Decimal | None = Field(default=None, ge=0.2, le=500)
    height_cm: Decimal | None = Field(default=None, ge=20, le=250)
    pain_score: int | None = Field(default=None, ge=0, le=10)
    consciousness_level: Literal["alert", "voice", "pain", "unresponsive", "not_assessed"] | None = None
    clinical_notes: str | None = Field(default=None, max_length=8000)

    @field_validator("chief_complaint")
    @classmethod
    def trim_triage_complaint(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("opd_triage_complaint_too_short")
        return value

    @field_validator("red_flag_note")
    @classmethod
    def trim_red_flag_note(cls, value):
        if value is not None:
            value = value.strip() or None
        return value

    @model_validator(mode="after")
    def validate_red_flag_note(self):
        if self.red_flag_present and (
            self.red_flag_note is None or len(self.red_flag_note) < 3
        ):
            raise ValueError("red_flag_requires_escalation_note")
        if self.red_flag_present and self.triage_level in {"standard", "non_urgent"}:
            raise ValueError("red_flag_requires_urgent_triage_level")
        if (
            self.systolic_bp is not None and self.diastolic_bp is not None
            and self.systolic_bp <= self.diastolic_bp
        ):
            raise ValueError("systolic_bp_must_exceed_diastolic_bp")
        return self


class OPDTriageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
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
    weight_kg: Decimal | None
    height_cm: Decimal | None
    pain_score: int | None
    consciousness_level: str | None
    clinical_notes: str | None
    assessed_by_user_id: UUID
    assessed_at: datetime


class OPDConsultationStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handover_note: str | None = Field(default=None, max_length=2000)


class OPDConsultationComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subjective: str | None = Field(default=None, max_length=12000)
    objective: str | None = Field(default=None, max_length=12000)
    assessment: str = Field(min_length=3, max_length=12000)
    plan: str = Field(min_length=3, max_length=12000)
    follow_up: str | None = Field(default=None, max_length=4000)

    @field_validator("assessment", "plan")
    @classmethod
    def trim_required_consultation_fields(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("consultation_assessment_or_plan_too_short")
        return value


class OPDConsultationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinician_user_id: UUID
    subjective: str | None
    objective: str | None
    assessment: str
    plan: str
    follow_up: str | None
    signed_at: datetime


class OPDDiagnosisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnosis_text: str = Field(min_length=2, max_length=500)
    concept_id: UUID | None = None
    certainty: Literal["suspected", "provisional", "confirmed", "ruled_out"] = "provisional"
    is_primary: bool = False

    @field_validator("diagnosis_text")
    @classmethod
    def trim_diagnosis_text(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("diagnosis_text_too_short")
        return value


class OPDDiagnosisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    diagnosis_text: str
    concept_id: UUID | None
    certainty: str
    is_primary: bool
    recorded_by_user_id: UUID
    recorded_at: datetime


class OPDDispositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: Literal[
        "discharged", "admission_requested", "referred",
        "transfer_requested", "left_without_being_seen",
    ]
    note: str = Field(min_length=3, max_length=4000)

    @field_validator("note")
    @classmethod
    def trim_disposition_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("opd_disposition_note_too_short")
        return value


class OPDPatientSummary(BaseModel):
    id: UUID
    medical_record_number: str
    given_name: str
    preferred_name: str | None
    family_name: str
    date_of_birth: date | None
    administrative_sex: str | None


class OPDQueueItemRead(BaseModel):
    visit: OPDVisitRead
    patient: OPDPatientSummary


class OPDVisitDetailRead(BaseModel):
    visit: OPDVisitRead
    patient: OPDPatientSummary
    triage: OPDTriageRead | None
    consultation: OPDConsultationRead | None
    diagnoses: list[OPDDiagnosisRead]
