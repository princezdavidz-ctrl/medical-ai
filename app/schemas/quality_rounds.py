from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SafetyRoundCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: UUID | None = None
    lead_user_id: UUID | None = None
    title: str = Field(min_length=3, max_length=180)
    scheduled_at: datetime

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.scheduled_at.tzinfo is None:
            raise ValueError("safety_round_schedule_must_be_timezone_aware")
        return self


class SafetyRoundComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=10, max_length=4000)


class SafetyRoundRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    department_id: UUID | None
    lead_user_id: UUID
    title: str
    scheduled_at: datetime
    conducted_at: datetime | None
    completed_at: datetime | None
    status: str
    summary: str | None
    created_by_user_id: UUID
    created_at: datetime


class SafetyRoundFindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_user_id: UUID
    severity: Literal["low", "moderate", "high", "critical"]
    description: str = Field(min_length=10, max_length=3000)
    due_at: datetime

    @model_validator(mode="after")
    def validate_due(self):
        if self.due_at.tzinfo is None:
            raise ValueError("finding_due_at_must_be_timezone_aware")
        return self


class SafetyRoundFindingResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution_note: str = Field(min_length=10, max_length=3000)


class SafetyRoundFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    round_id: UUID
    owner_user_id: UUID
    severity: str
    description: str
    due_at: datetime
    status: str
    resolution_note: str | None
    resolved_by_user_id: UUID | None
    resolved_at: datetime | None
    created_by_user_id: UUID
    created_at: datetime


class QualityIndicatorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=10, max_length=4000)
    unit: Literal["percent", "rate", "per_1000", "count"] = "percent"
    numerator_definition: str = Field(min_length=10, max_length=3000)
    denominator_definition: str = Field(min_length=10, max_length=3000)
    aggregation_period: Literal["daily", "weekly", "monthly", "quarterly", "annual"]


class QualityIndicatorDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    code: str
    version: int
    name: str
    description: str
    unit: str
    numerator_definition: str
    denominator_definition: str
    aggregation_period: str
    status: str
    created_by_user_id: UUID
    created_at: datetime


class QualityIndicatorMeasurementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period_start: datetime
    period_end: datetime
    numerator: int = Field(ge=0)
    denominator: int = Field(gt=0)
    data_source: str = Field(min_length=2, max_length=120)
    source_version: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_start.tzinfo is None or self.period_end.tzinfo is None:
            raise ValueError("indicator_period_must_be_timezone_aware")
        if self.period_end <= self.period_start:
            raise ValueError("indicator_period_end_must_follow_start")
        return self


class QualityIndicatorMeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    indicator_id: UUID
    period_start: datetime
    period_end: datetime
    numerator: int
    denominator: int
    value: float
    data_source: str
    source_version: str
    calculated_at: datetime
    created_by_user_id: UUID
