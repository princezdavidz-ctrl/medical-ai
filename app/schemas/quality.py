from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SafetyIncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: UUID | None = None
    patient_id: UUID | None = None
    encounter_id: UUID | None = None
    category: Literal["medication", "patient_fall", "diagnostic", "procedure", "infection", "equipment", "transfusion", "documentation", "communication", "security", "other"]
    occurred_at: datetime
    summary: str = Field(min_length=10, max_length=4000)
    immediate_actions: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_event_time(self):
        if self.occurred_at.tzinfo is None:
            raise ValueError("incident_time_must_be_timezone_aware")
        if (self.patient_id is None) != (self.encounter_id is None) and self.encounter_id is not None:
            raise ValueError("encounter_requires_patient_reference")
        return self


class SafetyIncidentTriage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity: Literal["low", "moderate", "high", "critical", "unclassified"]
    harm_level: Literal["none", "mild", "moderate", "severe", "death", "unknown"]


class SafetyIncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    department_id: UUID | None
    patient_id: UUID | None
    encounter_id: UUID | None
    reporter_user_id: UUID | None
    reporter_confidential: bool
    category: str
    severity: str
    harm_level: str
    status: str
    occurred_at: datetime
    reported_at: datetime
    summary: str
    immediate_actions: str | None
    created_at: datetime
    updated_at: datetime


class SafetyInvestigationAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_to_user_id: UUID


class SafetyInvestigationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: str = Field(min_length=20, max_length=10000)
    contributing_factors: list[str] = Field(min_length=1, max_length=30)


class SafetyInvestigationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    incident_id: UUID
    assigned_to_user_id: UUID
    status: str
    findings: str | None
    contributing_factors: list[str]
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CAPACreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_user_id: UUID
    action_description: str = Field(min_length=10, max_length=5000)
    due_at: datetime

    @model_validator(mode="after")
    def validate_due_at(self):
        if self.due_at.tzinfo is None:
            raise ValueError("capa_due_at_must_be_timezone_aware")
        return self


class CAPAEvidenceSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_reference: str = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class CAPAEffectivenessReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    effectiveness_review: str = Field(min_length=20, max_length=5000)


class CAPARead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    incident_id: UUID
    owner_user_id: UUID
    action_description: str
    due_at: datetime
    status: str
    evidence_reference: str | None
    effectiveness_review: str | None
    effectiveness_reviewer_user_id: UUID | None
    effectiveness_reviewed_at: datetime | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
