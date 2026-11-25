from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TelemedicineSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    provider_user_id: UUID
    department_id: UUID
    consent_id: UUID
    visit_reason: str = Field(min_length=3, max_length=500)
    scheduled_start: datetime
    scheduled_end: datetime

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.scheduled_start.tzinfo is None or self.scheduled_end.tzinfo is None:
            raise ValueError("timezone_aware_schedule_required")
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("session_end_must_follow_start")
        if (self.scheduled_end - self.scheduled_start).total_seconds() > 7200:
            raise ValueError("telemedicine_session_maximum_two_hours")
        return self


class TelemedicinePatientReady(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_location_reference: str = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)
    emergency_contact_reference: str = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)
    patient_identity_confirmed: Literal[True]
    privacy_confirmed: Literal[True]
    emergency_plan_acknowledged: Literal[True]


class TelemedicineNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_type: Literal["consultation", "assessment", "plan", "follow_up", "safety_plan", "referral"]
    note_text: str = Field(min_length=10, max_length=20000)


class TelemedicineCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=1000)


class TelemedicineSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    provider_employee_profile_id: UUID
    provider_user_id: UUID
    department_id: UUID
    consent_id: UUID
    encounter_id: UUID | None
    visit_reason: str
    scheduled_start: datetime
    scheduled_end: datetime
    status: str
    patient_ready_at: datetime | None
    patient_ready_by_user_id: UUID | None
    patient_location_reference: str | None
    emergency_contact_reference: str | None
    safety_confirmed_at: datetime | None
    safety_confirmed_by_user_id: UUID | None
    patient_identity_confirmed: bool
    privacy_confirmed: bool
    emergency_plan_acknowledged: bool
    started_at: datetime | None
    started_by_user_id: UUID | None
    ended_at: datetime | None
    ended_by_user_id: UUID | None
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class TelemedicineNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    session_id: UUID
    encounter_id: UUID
    patient_id: UUID
    author_user_id: UUID
    note_type: str
    note_text: str
    signed_at: datetime
    created_at: datetime
