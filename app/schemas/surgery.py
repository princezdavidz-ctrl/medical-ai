from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TheatreRoomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: UUID
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=40)
    theatre_type: Literal["general", "orthopedic", "cardiac", "obstetric", "neurosurgical", "other"]

    @field_validator("name", "code")
    @classmethod
    def normalize_theatre_fields(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("theatre_name_or_code_too_short")
        return value


class TheatreRoomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    name: str
    code: str
    theatre_type: str
    status: str


class SurgicalCaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encounter_id: UUID
    theatre_room_id: UUID
    planned_procedure: str = Field(min_length=3, max_length=2000)
    urgency: Literal["elective", "urgent", "emergency"]
    scheduled_start_at: datetime
    scheduled_end_at: datetime

    @field_validator("planned_procedure")
    @classmethod
    def normalize_procedure(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("planned_procedure_too_short")
        return value

    @model_validator(mode="after")
    def validate_schedule(self):
        for value in (self.scheduled_start_at, self.scheduled_end_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("surgical_schedule_must_include_timezone")
        if self.scheduled_end_at <= self.scheduled_start_at:
            raise ValueError("surgical_schedule_end_must_follow_start")
        if self.scheduled_end_at - self.scheduled_start_at > timedelta(hours=24):
            raise ValueError("surgical_schedule_duration_exceeds_limit")
        if self.scheduled_start_at < datetime.now(timezone.utc) - timedelta(minutes=5):
            raise ValueError("surgical_schedule_cannot_start_in_past")
        return self


class SurgicalCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    theatre_room_id: UUID
    surgeon_user_id: UUID
    requested_by_user_id: UUID
    planned_procedure: str
    urgency: str
    status: str
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    actual_started_at: datetime | None
    actual_ended_at: datetime | None
    cancellation_reason: str | None
    cancelled_at: datetime | None


class SurgicalTeamAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_user_id: UUID
    assignment_reason: str = Field(min_length=3, max_length=500)

    @field_validator("assignment_reason")
    @classmethod
    def normalize_assignment_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("surgical_assignment_reason_too_short")
        return value


class SurgicalSafetyChecklistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal["sign_in", "time_out", "sign_out"]
    patient_identity_confirmed: bool
    procedure_confirmed: bool
    site_confirmed: bool
    consent_verified: bool
    allergies_reviewed: bool
    anesthesia_safety_confirmed: bool
    equipment_ready: bool
    counts_confirmed: bool
    notes: str | None = Field(default=None, max_length=4000)


class SurgicalSafetyChecklistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    surgical_case_id: UUID
    phase: str
    revision: int
    patient_identity_confirmed: bool
    procedure_confirmed: bool
    site_confirmed: bool
    consent_verified: bool
    allergies_reviewed: bool
    anesthesia_safety_confirmed: bool
    equipment_ready: bool
    counts_confirmed: bool
    recorded_by_user_id: UUID
    notes: str | None
    recorded_at: datetime


class AnesthesiaRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anesthesia_type: Literal["general", "regional", "local", "sedation", "combined"]
    asa_class: int = Field(ge=1, le=5)
    airway_method: str | None = Field(default=None, max_length=160)
    pre_anesthesia_assessment: str = Field(min_length=3, max_length=10000)
    intraoperative_notes: str | None = Field(default=None, max_length=12000)
    complications: str | None = Field(default=None, max_length=8000)
    started_at: datetime

    @field_validator("pre_anesthesia_assessment")
    @classmethod
    def normalize_assessment(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("pre_anesthesia_assessment_too_short")
        return value

    @field_validator("started_at")
    @classmethod
    def validate_started_at(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("anesthesia_timestamp_must_include_timezone")
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("anesthesia_timestamp_cannot_be_in_future")
        return value


class AnesthesiaRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    surgical_case_id: UUID
    anesthesia_provider_user_id: UUID
    anesthesia_type: str
    asa_class: int
    airway_method: str | None
    pre_anesthesia_assessment: str
    intraoperative_notes: str | None
    complications: str | None
    started_at: datetime
    ended_at: datetime | None


class SurgicalEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal["incision", "procedure_step", "specimen", "count_check", "closure", "complication", "handover", "other"]
    description: str = Field(min_length=3, max_length=8000)
    performed_at: datetime

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("surgical_event_description_too_short")
        return value

    @field_validator("performed_at")
    @classmethod
    def validate_performed_at(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("surgical_event_timestamp_must_include_timezone")
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("surgical_event_timestamp_cannot_be_in_future")
        return value


class SurgicalEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    performed_by_user_id: UUID
    event_type: str
    description: str
    performed_at: datetime
    recorded_at: datetime


class SurgicalNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_type: Literal["operative", "post_op", "handover", "incident", "other"]
    note_text: str = Field(min_length=3, max_length=16000)

    @field_validator("note_text")
    @classmethod
    def normalize_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("surgical_note_too_short")
        return value


class SurgicalNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_user_id: UUID
    note_type: str
    note_text: str
    signed_at: datetime


class SurgicalCaseCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=4000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("surgical_cancellation_reason_too_short")
        return value


class SurgicalCaseDetailRead(BaseModel):
    surgical_case: SurgicalCaseRead
    checklists: list[SurgicalSafetyChecklistRead]
    anesthesia: AnesthesiaRecordRead | None
    events: list[SurgicalEventRead]
    notes: list[SurgicalNoteRead]
