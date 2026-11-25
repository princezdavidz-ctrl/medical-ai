from datetime import datetime, time
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ShiftTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: UUID | None = None
    code: str = Field(min_length=2, max_length=40, pattern="^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(pattern="^(day|evening|night|on_call|other)$")
    start_time: time
    end_time: time
    break_minutes: int = Field(default=0, ge=0, le=240)


class ShiftTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    category: str | None = Field(default=None, pattern="^(day|evening|night|on_call|other)$")
    start_time: time | None = None
    end_time: time | None = None
    break_minutes: int | None = Field(default=None, ge=0, le=240)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class ShiftTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    department_id: UUID | None
    code: str
    name: str
    category: str
    start_time: time
    end_time: time
    break_minutes: int
    status: str
    created_by_user_id: UUID
    created_at: datetime


class ShiftAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_profile_id: UUID
    shift_template_id: UUID
    department_id: UUID | None = None
    starts_at: datetime
    ends_at: datetime
    note: str | None = Field(default=None, max_length=1000)


class ShiftAssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str | None = Field(default=None, pattern="^(confirmed|cancelled)$")
    note: str | None = Field(default=None, max_length=1000)


class ShiftAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    employee_profile_id: UUID
    staff_user_id: UUID
    department_id: UUID | None
    shift_template_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: str
    assigned_by_user_id: UUID
    note: str | None
    created_at: datetime
    updated_at: datetime


class ShiftSwapRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_user_id: UUID
    reason: str = Field(min_length=5, max_length=1000)


class ShiftSwapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accept: bool
    note: str | None = Field(default=None, max_length=1000)


class ShiftSwapDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = Field(default=None, max_length=1000)


class ShiftSwapRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    shift_assignment_id: UUID
    requester_user_id: UUID
    target_user_id: UUID
    reason: str
    status: str
    responded_by_user_id: UUID | None
    responded_at: datetime | None
    decided_by_user_id: UUID | None
    decided_at: datetime | None
    decision_note: str | None
    created_at: datetime


class AttendanceCheckOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, max_length=1000)


class AttendanceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = Field(default=None, max_length=1000)


class ShiftAttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    shift_assignment_id: UUID
    staff_user_id: UUID
    check_in_at: datetime
    check_out_at: datetime | None
    source: str
    status: str
    note: str | None
    decided_by_user_id: UUID | None
    decided_at: datetime | None
    decision_note: str | None
    created_at: datetime


class AttendanceResubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_in_at: datetime
    check_out_at: datetime
    note: str | None = Field(default=None, max_length=1000)


class ShiftSwapCancellation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=1000)
