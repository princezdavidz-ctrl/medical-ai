from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_id: UUID
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=40)
    ward_type: Literal["general", "medical", "surgical", "maternity", "pediatric", "icu", "other"]

    @field_validator("name", "code")
    @classmethod
    def normalize_ward_fields(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("ward_name_or_code_too_short")
        return value


class WardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    name: str
    code: str
    ward_type: str
    status: str


class BedCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bed_number: str = Field(min_length=1, max_length=40)
    bed_type: Literal["standard", "isolation", "high_dependency", "critical_care", "maternity", "pediatric", "other"] = "standard"
    isolation_capable: bool = False
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("bed_number")
    @classmethod
    def normalize_bed_number(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("bed_number_required")
        return value


class BedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ward_id: UUID
    bed_number: str
    bed_type: str
    status: str
    isolation_capable: bool
    notes: str | None


class AdmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_encounter_id: UUID
    ward_id: UUID
    admission_reason: str = Field(min_length=3, max_length=8000)

    @field_validator("admission_reason")
    @classmethod
    def normalize_admission_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("admission_reason_too_short")
        return value


class AdmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    encounter_id: UUID
    source_encounter_id: UUID | None
    ward_id: UUID
    requested_by_user_id: UUID
    accepted_by_user_id: UUID | None
    discharged_by_user_id: UUID | None
    admission_reason: str
    status: str
    requested_at: datetime
    accepted_at: datetime | None
    admitted_at: datetime | None
    discharged_at: datetime | None
    discharge_summary: str | None


class BedAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bed_id: UUID


class BedAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    admission_id: UUID
    bed_id: UUID
    assigned_by_user_id: UUID
    released_by_user_id: UUID | None
    status: str
    assigned_at: datetime
    released_at: datetime | None


class CareTeamAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_user_id: UUID
    assignment_reason: str = Field(min_length=3, max_length=500)

    @field_validator("assignment_reason")
    @classmethod
    def normalize_assignment_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("assignment_reason_too_short")
        return value


class InpatientDischargeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discharge_summary: str = Field(min_length=3, max_length=16000)

    @field_validator("discharge_summary")
    @classmethod
    def normalize_discharge_summary(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("discharge_summary_too_short")
        return value
