from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MaternityEpisodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID
    encounter_id: UUID
    department_id: UUID
    pregnancy_number: int = Field(ge=1, le=30)
    gravida: int = Field(ge=1, le=30)
    para: int = Field(ge=0, le=30)
    last_menstrual_period: date | None = None
    estimated_due_date: date | None = None

    @model_validator(mode="after")
    def validate_pregnancy(self):
        if self.para > self.gravida:
            raise ValueError("para_cannot_exceed_gravida")
        if self.last_menstrual_period is not None and self.last_menstrual_period > date.today():
            raise ValueError("last_menstrual_period_cannot_be_in_future")
        if (
            self.last_menstrual_period is not None
            and self.estimated_due_date is not None
            and self.estimated_due_date <= self.last_menstrual_period
        ):
            raise ValueError("estimated_due_date_must_follow_lmp")
        return self


class MaternityEpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    department_id: UUID
    pregnancy_number: int
    gravida: int
    para: int
    last_menstrual_period: date | None
    estimated_due_date: date | None
    pregnancy_status: str
    status: str
    created_by_user_id: UUID
    created_at: datetime
    closed_at: datetime | None
    closed_reason: str | None
    pregnancy_end_reason: str | None


class MaternityAntenatalVisitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gestational_age_weeks: int = Field(ge=0, le=45)
    gestational_age_days: int = Field(default=0, ge=0, le=6)
    systolic_bp: Decimal | None = Field(default=None, ge=30, le=300)
    diastolic_bp: Decimal | None = Field(default=None, ge=20, le=200)
    weight_kg: Decimal | None = Field(default=None, ge=0.2, le=500)
    fetal_heart_rate: int | None = Field(default=None, ge=50, le=240)
    fundal_height_cm: Decimal | None = Field(default=None, ge=0, le=60)
    fetal_movement_reported: bool | None = None
    notes: str | None = Field(default=None, max_length=8000)
    visited_at: datetime

    @model_validator(mode="after")
    def validate_visit(self):
        if self.systolic_bp is not None and self.diastolic_bp is not None:
            if self.systolic_bp <= self.diastolic_bp:
                raise ValueError("systolic_bp_must_exceed_diastolic_bp")
        if self.visited_at.tzinfo is None or self.visited_at.utcoffset() is None:
            raise ValueError("antenatal_visit_timestamp_must_include_timezone")
        if self.visited_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("antenatal_visit_timestamp_cannot_be_in_future")
        return self


class MaternityAntenatalVisitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_user_id: UUID
    gestational_age_weeks: int
    gestational_age_days: int
    systolic_bp: Decimal | None
    diastolic_bp: Decimal | None
    weight_kg: Decimal | None
    fetal_heart_rate: int | None
    fundal_height_cm: Decimal | None
    fetal_movement_reported: bool | None
    notes: str | None
    visited_at: datetime
    recorded_at: datetime


class LaborRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onset_type: Literal["spontaneous", "induced", "augmented", "other"]
    membrane_status: Literal["intact", "ruptured", "unknown"] = "unknown"
    presentation: Literal["cephalic", "breech", "transverse", "other", "unknown"] = "unknown"
    started_at: datetime

    @field_validator("started_at")
    @classmethod
    def validate_labor_start(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("labor_start_timestamp_must_include_timezone")
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("labor_start_timestamp_cannot_be_in_future")
        return value


class LaborRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    episode_id: UUID
    lead_midwife_user_id: UUID
    status: str
    onset_type: str
    membrane_status: str
    presentation: str
    started_at: datetime
    ended_at: datetime | None


class LaborObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labor_stage: Literal["latent", "active", "second_stage"]
    cervical_dilation_cm: Decimal | None = Field(default=None, ge=0, le=10)
    fetal_heart_rate: int | None = Field(default=None, ge=50, le=240)
    contractions_per_10_min: int | None = Field(default=None, ge=0, le=10)
    contraction_duration_seconds: int | None = Field(default=None, ge=0, le=300)
    maternal_heart_rate: int | None = Field(default=None, ge=1, le=300)
    systolic_bp: Decimal | None = Field(default=None, ge=30, le=300)
    diastolic_bp: Decimal | None = Field(default=None, ge=20, le=200)
    temperature_c: Decimal | None = Field(default=None, ge=25, le=45)
    spo2_percent: Decimal | None = Field(default=None, ge=0, le=100)
    membrane_status: Literal["intact", "ruptured", "unknown"] | None = None
    amniotic_fluid_description: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=8000)
    observed_at: datetime

    @model_validator(mode="after")
    def validate_labor_observation(self):
        if self.systolic_bp is not None and self.diastolic_bp is not None:
            if self.systolic_bp <= self.diastolic_bp:
                raise ValueError("systolic_bp_must_exceed_diastolic_bp")
        values = (
            self.cervical_dilation_cm, self.fetal_heart_rate,
            self.contractions_per_10_min, self.contraction_duration_seconds,
            self.maternal_heart_rate, self.systolic_bp, self.diastolic_bp,
            self.temperature_c, self.spo2_percent, self.membrane_status,
        )
        if not any(value is not None for value in values):
            raise ValueError("labor_observation_requires_measurement")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("labor_observation_timestamp_must_include_timezone")
        if self.observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("labor_observation_timestamp_cannot_be_in_future")
        return self


class LaborObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recorded_by_user_id: UUID
    labor_stage: str
    cervical_dilation_cm: Decimal | None
    fetal_heart_rate: int | None
    contractions_per_10_min: int | None
    contraction_duration_seconds: int | None
    maternal_heart_rate: int | None
    systolic_bp: Decimal | None
    diastolic_bp: Decimal | None
    temperature_c: Decimal | None
    spo2_percent: Decimal | None
    membrane_status: str | None
    amniotic_fluid_description: str | None
    notes: str | None
    observed_at: datetime
    recorded_at: datetime


class DeliveryRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_mode: Literal["spontaneous_vaginal", "assisted_vaginal", "cesarean", "breech", "other"]
    surgical_case_id: UUID | None = None
    delivered_at: datetime
    placenta_delivered_at: datetime | None = None
    estimated_blood_loss_ml: Decimal | None = Field(default=None, ge=0, le=50000)
    complications: str | None = Field(default=None, max_length=12000)

    @model_validator(mode="after")
    def validate_delivery_times(self):
        if self.delivered_at.tzinfo is None or self.delivered_at.utcoffset() is None:
            raise ValueError("delivery_timestamp_must_include_timezone")
        if self.placenta_delivered_at is not None:
            if self.placenta_delivered_at.tzinfo is None or self.placenta_delivered_at.utcoffset() is None:
                raise ValueError("placenta_timestamp_must_include_timezone")
            if self.placenta_delivered_at < self.delivered_at:
                raise ValueError("placenta_timestamp_before_delivery")
        if self.delivered_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("delivery_timestamp_cannot_be_in_future")
        return self


class DeliveryRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    labor_record_id: UUID | None
    episode_id: UUID
    surgical_case_id: UUID | None
    delivered_by_user_id: UUID
    delivery_mode: str
    delivered_at: datetime
    placenta_delivered_at: datetime | None
    estimated_blood_loss_ml: Decimal | None
    complications: str | None
    recorded_at: datetime


class NewbornRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    birth_order: int = Field(ge=1, le=20)
    sex: Literal["female", "male", "intersex", "unknown"] = "unknown"
    outcome: Literal["live_birth", "stillbirth", "neonatal_death"]
    birth_at: datetime
    birth_weight_g: Decimal | None = Field(default=None, ge=100, le=10000)
    length_cm: Decimal | None = Field(default=None, ge=10, le=100)
    head_circumference_cm: Decimal | None = Field(default=None, ge=10, le=70)
    apgar_1_minute: int | None = Field(default=None, ge=0, le=10)
    apgar_5_minute: int | None = Field(default=None, ge=0, le=10)
    apgar_10_minute: int | None = Field(default=None, ge=0, le=10)
    resuscitation_required: bool = False
    notes: str | None = Field(default=None, max_length=8000)

    @field_validator("birth_at")
    @classmethod
    def validate_birth_at(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("newborn_birth_timestamp_must_include_timezone")
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("newborn_birth_timestamp_cannot_be_in_future")
        return value


class NewbornRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    delivery_id: UUID
    mother_patient_id: UUID
    newborn_patient_id: UUID | None
    birth_order: int
    sex: str
    outcome: str
    birth_at: datetime
    birth_weight_g: Decimal | None
    length_cm: Decimal | None
    head_circumference_cm: Decimal | None
    apgar_1_minute: int | None
    apgar_5_minute: int | None
    apgar_10_minute: int | None
    resuscitation_required: bool
    notes: str | None


class PostpartumObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maternal_heart_rate: int | None = Field(default=None, ge=1, le=300)
    systolic_bp: Decimal | None = Field(default=None, ge=30, le=300)
    diastolic_bp: Decimal | None = Field(default=None, ge=20, le=200)
    temperature_c: Decimal | None = Field(default=None, ge=25, le=45)
    spo2_percent: Decimal | None = Field(default=None, ge=0, le=100)
    estimated_blood_loss_ml: Decimal | None = Field(default=None, ge=0, le=50000)
    uterine_tone: Literal["firm", "boggy", "not_assessed"] = "not_assessed"
    lochia: Literal["normal", "heavy", "not_assessed"] = "not_assessed"
    breastfeeding_initiated: bool | None = None
    notes: str | None = Field(default=None, max_length=8000)
    observed_at: datetime

    @model_validator(mode="after")
    def validate_postpartum(self):
        if self.systolic_bp is not None and self.diastolic_bp is not None:
            if self.systolic_bp <= self.diastolic_bp:
                raise ValueError("systolic_bp_must_exceed_diastolic_bp")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("postpartum_timestamp_must_include_timezone")
        if self.observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("postpartum_timestamp_cannot_be_in_future")
        return self


class PostpartumObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recorded_by_user_id: UUID
    maternal_heart_rate: int | None
    systolic_bp: Decimal | None
    diastolic_bp: Decimal | None
    temperature_c: Decimal | None
    spo2_percent: Decimal | None
    estimated_blood_loss_ml: Decimal | None
    uterine_tone: str
    lochia: str
    breastfeeding_initiated: bool | None
    notes: str | None
    observed_at: datetime
    recorded_at: datetime


class NewbornObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_c: Decimal | None = Field(default=None, ge=25, le=45)
    heart_rate: int | None = Field(default=None, ge=1, le=300)
    respiratory_rate: int | None = Field(default=None, ge=1, le=150)
    spo2_percent: Decimal | None = Field(default=None, ge=0, le=100)
    feeding_status: Literal["breastfeeding", "expressed_milk", "formula", "not_feeding", "not_assessed"] = "not_assessed"
    urine_output_count: int | None = Field(default=None, ge=0, le=100)
    stool_count: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=8000)
    observed_at: datetime

    @model_validator(mode="after")
    def validate_newborn_observation(self):
        values = (
            self.temperature_c, self.heart_rate, self.respiratory_rate,
            self.spo2_percent, self.urine_output_count, self.stool_count,
        )
        if not any(value is not None for value in values) and self.feeding_status == "not_assessed":
            raise ValueError("newborn_observation_requires_measurement")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("newborn_observation_timestamp_must_include_timezone")
        if self.observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("newborn_observation_timestamp_cannot_be_in_future")
        return self


class NewbornObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recorded_by_user_id: UUID
    temperature_c: Decimal | None
    heart_rate: int | None
    respiratory_rate: int | None
    spo2_percent: Decimal | None
    feeding_status: str
    urine_output_count: int | None
    stool_count: int | None
    notes: str | None
    observed_at: datetime
    recorded_at: datetime


class MaternityNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_type: Literal["antenatal", "labor", "delivery", "postpartum", "handover", "other"]
    note_text: str = Field(min_length=3, max_length=16000)

    @field_validator("note_text")
    @classmethod
    def normalize_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("maternity_note_too_short")
        return value


class MaternityNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_user_id: UUID
    note_type: str
    note_text: str
    signed_at: datetime


class NewbornPatientLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID




class MaternityEpisodeEnd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["miscarriage", "ectopic", "termination", "other"]
    note: str = Field(min_length=3, max_length=8000)

    @field_validator("note")
    @classmethod
    def normalize_end_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("pregnancy_end_note_too_short")
        return value


class MaternityEpisodeClose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=4000)

    @field_validator("reason")
    @classmethod
    def normalize_close_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("maternity_close_reason_too_short")
        return value



class MaternityTeamAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_user_id: UUID
    assignment_reason: str = Field(min_length=3, max_length=500)

    @field_validator("assignment_reason")
    @classmethod
    def normalize_assignment_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("maternity_assignment_reason_too_short")
        return value


class MaternityEpisodeDetailRead(BaseModel):
    episode: MaternityEpisodeRead
    antenatal_visits: list[MaternityAntenatalVisitRead]
    labor: LaborRecordRead | None
    labor_observations: list[LaborObservationRead]
    delivery: DeliveryRecordRead | None
    newborns: list[NewbornRecordRead]
    postpartum_observations: list[PostpartumObservationRead]
    notes: list[MaternityNoteRead]
