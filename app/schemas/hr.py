from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmployeeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    department_id: UUID | None = None
    employee_number: str = Field(min_length=2, max_length=80)
    job_title: str = Field(min_length=2, max_length=160)
    employment_type: str = Field(pattern="^(permanent|contract|locum|intern|volunteer|other)$")
    start_date: datetime
    manager_user_id: UUID | None = None

    @field_validator("employee_number", "job_title")
    @classmethod
    def normalize_text(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("value_required")
        return value


class EmployeeStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employment_status: str = Field(pattern="^(active|on_leave|suspended|terminated)$")
    end_date: datetime | None = None


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    department_id: UUID | None
    employee_number: str
    job_title: str
    employment_type: str
    employment_status: str
    start_date: datetime
    end_date: datetime | None
    manager_user_id: UUID | None
    created_at: datetime


class CredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential_type: str = Field(min_length=2, max_length=100)
    credential_number: str = Field(min_length=2, max_length=160)
    issuing_body: str = Field(min_length=2, max_length=180)
    valid_from: datetime
    valid_until: datetime | None = None
    evidence_reference: str | None = Field(default=None, max_length=160)


class CredentialDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str = Field(pattern="^(verified|rejected|expired)$")
    note: str = Field(min_length=3, max_length=1000)


class CredentialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    employee_profile_id: UUID
    credential_type: str
    credential_number: str
    issuing_body: str
    valid_from: datetime
    valid_until: datetime | None
    verification_status: str
    evidence_reference: str | None
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    created_at: datetime


class LeaveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    leave_type: str = Field(min_length=2, max_length=40)
    start_at: datetime
    end_at: datetime
    reason: str = Field(min_length=3, max_length=2000)


class LeaveDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str = Field(pattern="^(approved|rejected)$")
    decision_note: str = Field(min_length=3, max_length=2000)


class LeaveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    employee_profile_id: UUID
    leave_type: str
    start_at: datetime
    end_at: datetime
    reason: str
    status: str
    requested_by_user_id: UUID
    decided_by_user_id: UUID | None
    decided_at: datetime | None
    decision_note: str | None
    created_at: datetime
