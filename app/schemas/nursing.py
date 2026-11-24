from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NursingAssessmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_type: Literal["admission", "shift", "focused", "discharge"]
    general_condition: str | None = Field(default=None, max_length=500)
    mental_status: str | None = Field(default=None, max_length=500)
    mobility_status: str | None = Field(default=None, max_length=500)
    skin_assessment: str | None = Field(default=None, max_length=8000)
    pain_score: int | None = Field(default=None, ge=0, le=10)
    fall_risk_level: Literal["low", "moderate", "high", "not_assessed"] | None = None
    pressure_injury_risk_level: Literal["low", "moderate", "high", "not_assessed"] | None = None
    nutrition_concerns: str | None = Field(default=None, max_length=4000)
    nursing_concerns: str | None = Field(default=None, max_length=8000)


class NursingAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    department_id: UUID
    assessed_by_user_id: UUID
    assessment_type: str
    general_condition: str | None
    mental_status: str | None
    mobility_status: str | None
    skin_assessment: str | None
    pain_score: int | None
    fall_risk_level: str | None
    pressure_injury_risk_level: str | None
    nutrition_concerns: str | None
    nursing_concerns: str | None
    assessed_at: datetime


class NursingObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heart_rate: Decimal | None = Field(default=None, ge=1, le=300)
    respiratory_rate: Decimal | None = Field(default=None, ge=1, le=100)
    temperature_c: Decimal | None = Field(default=None, ge=25, le=45)
    systolic_bp: Decimal | None = Field(default=None, ge=30, le=300)
    diastolic_bp: Decimal | None = Field(default=None, ge=20, le=200)
    spo2_percent: Decimal | None = Field(default=None, ge=0, le=100)
    pain_score: int | None = Field(default=None, ge=0, le=10)
    consciousness_level: Literal["alert", "voice", "pain", "unresponsive", "not_assessed"] | None = None
    oxygen_delivery: str | None = Field(default=None, max_length=120)
    intake_ml: Decimal | None = Field(default=None, ge=0, le=100000)
    output_ml: Decimal | None = Field(default=None, ge=0, le=100000)
    notes: str | None = Field(default=None, max_length=4000)
    observed_at: datetime

    @model_validator(mode="after")
    def validate_observation(self):
        if self.systolic_bp is not None and self.diastolic_bp is not None:
            if self.systolic_bp <= self.diastolic_bp:
                raise ValueError("systolic_bp_must_exceed_diastolic_bp")
        if not any(value is not None for key, value in self.model_dump().items() if key != "observed_at"):
            raise ValueError("nursing_observation_requires_at_least_one_measurement")
        return self


class NursingObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    recorded_by_user_id: UUID
    heart_rate: Decimal | None
    respiratory_rate: Decimal | None
    temperature_c: Decimal | None
    systolic_bp: Decimal | None
    diastolic_bp: Decimal | None
    spo2_percent: Decimal | None
    pain_score: int | None
    consciousness_level: str | None
    oxygen_delivery: str | None
    intake_ml: Decimal | None
    output_ml: Decimal | None
    notes: str | None
    observed_at: datetime
    recorded_at: datetime


class NursingNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_type: Literal["shift_handover", "progress", "incident", "discharge", "other"]
    note_text: str = Field(min_length=3, max_length=16000)

    @field_validator("note_text")
    @classmethod
    def normalize_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("nursing_note_too_short")
        return value


class NursingNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    author_user_id: UUID
    note_type: str
    note_text: str
    signed_at: datetime


class NursingCarePlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nursing_diagnosis: str = Field(min_length=3, max_length=1000)
    goals: str = Field(min_length=3, max_length=12000)
    interventions: str = Field(min_length=3, max_length=12000)

    @field_validator("nursing_diagnosis", "goals", "interventions")
    @classmethod
    def normalize_care_plan_text(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("nursing_care_plan_field_too_short")
        return value


class NursingCarePlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    department_id: UUID
    created_by_user_id: UUID
    nursing_diagnosis: str
    goals: str
    interventions: str
    status: str
    created_at: datetime
    updated_at: datetime


class NursingCarePlanReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["ongoing", "achieved", "partially_achieved", "not_achieved", "escalated"]
    evaluation_note: str = Field(min_length=3, max_length=8000)

    @field_validator("evaluation_note")
    @classmethod
    def normalize_evaluation_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("nursing_evaluation_note_too_short")
        return value


class NursingCarePlanReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    care_plan_id: UUID
    reviewed_by_user_id: UUID
    outcome: str
    evaluation_note: str
    reviewed_at: datetime
