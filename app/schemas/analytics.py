from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]+$")
    report_key: Literal["patient_flow", "bed_occupancy", "emergency_volume", "billing_summary", "quality_safety", "compliance_overview"]
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=10, max_length=4000)
    data_domain: Literal["clinical", "operations", "finance", "quality", "compliance"]
    required_roles: list[str] = Field(min_length=1, max_length=30)
    department_scoped: bool = False
    definition: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_definition(self):
        forbidden = {"sql", "query", "table", "join", "raw_sql"}
        if forbidden.intersection({str(key).casefold() for key in self.definition}):
            raise ValueError("report_definition_must_not_contain_executable_sql")
        return self


class ReportDefinitionPublish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publish_note: str = Field(min_length=10, max_length=1000)


class ReportDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    report_code: str
    version: int
    report_key: str
    title: str
    description: str
    data_domain: str
    required_roles: list[str]
    department_scoped: bool
    definition: dict
    status: str
    created_by_user_id: UUID
    published_by_user_id: UUID | None
    published_at: datetime | None
    created_at: datetime


class ReportRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_at: datetime | None = None
    end_at: datetime | None = None
    department_id: UUID | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if self.start_at is not None and self.start_at.tzinfo is None:
            raise ValueError("report_start_must_be_timezone_aware")
        if self.end_at is not None and self.end_at.tzinfo is None:
            raise ValueError("report_end_must_be_timezone_aware")
        if self.start_at is not None and self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("report_end_must_follow_start")
        return self


class ReportRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    definition_id: UUID
    requested_by_user_id: UUID
    filters: dict
    result_summary: dict
    source_versions: dict
    status: str
    generated_at: datetime
    expires_at: datetime


class ReportExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["csv", "pdf"]


class ReportExportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    run_id: UUID
    requested_by_user_id: UUID
    format: str
    status: str
    output_reference: str | None
    expires_at: datetime
    created_at: datetime
