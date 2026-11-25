from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ClinicalStaffProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_profile_id: UUID
    clinical_role: str = Field(pattern="^(physician|nurse|midwife|pharmacist|clinical_officer|dentist|therapist|radiographer|laboratory_scientist|other)$")
    specialty: str | None = Field(default=None, max_length=160)
    professional_title: str = Field(min_length=2, max_length=160)
    registration_number: str = Field(min_length=2, max_length=120)
    licensing_body: str = Field(min_length=2, max_length=160)
    license_expires_at: datetime | None = None


class ClinicalStaffProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    user_id: UUID
    employee_profile_id: UUID
    clinical_role: str
    specialty: str | None
    professional_title: str
    registration_number: str
    licensing_body: str
    license_expires_at: datetime | None
    status: str
    evidence_reference: str | None
    rejection_reason: str | None
    suspension_reason: str | None
    submitted_by_user_id: UUID
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ClinicalStaffVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(verified|rejected)$")
    evidence_reference: str | None = Field(default=None, pattern="^vault://[0-9a-fA-F-]{36}$")
    rejection_reason: str | None = Field(default=None, min_length=5, max_length=1000)


class ClinicalStaffSuspension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=1000)


class ClinicalStaffReinstatement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_reference: str = Field(pattern="^vault://[0-9a-fA-F-]{36}$")
    review_note: str = Field(min_length=5, max_length=1000)


class CareTeamAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    staff_user_id: UUID
    department_id: UUID | None = None
    care_role: str = Field(pattern="^(attending_physician|consultant|primary_nurse|midwife|pharmacist|case_manager|allied_health|other)$")
    access_scope: list[str] = Field(default_factory=lambda: ["profile", "encounters"], min_length=1)
    ends_at: datetime | None = None


class CareTeamAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    staff_user_id: UUID
    department_id: UUID | None
    care_role: str
    access_scope: list[str]
    status: str
    starts_at: datetime
    ends_at: datetime | None
    assigned_by_user_id: UUID
    ended_by_user_id: UUID | None
    ended_at: datetime | None
    end_reason: str | None
    created_at: datetime


class CareTeamAssignmentEnd(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(ended|revoked)$")
    reason: str = Field(min_length=5, max_length=1000)


class StaffTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_to_user_id: UUID
    patient_id: UUID | None = None
    encounter_id: UUID | None = None
    department_id: UUID | None = None
    task_type: str = Field(pattern="^(review_lab_result|sign_note|medication_review|discharge_planning|follow_up|referral|care_coordination|other)$")
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    due_at: datetime | None = None


class StaffTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(in_progress|completed|cancelled)$")
    completion_note: str | None = Field(default=None, max_length=1000)


class StaffTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    assigned_to_user_id: UUID
    created_by_user_id: UUID
    patient_id: UUID | None
    encounter_id: UUID | None
    department_id: UUID | None
    task_type: str
    title: str
    description: str | None
    priority: str
    status: str
    due_at: datetime | None
    completed_by_user_id: UUID | None
    completed_at: datetime | None
    completion_note: str | None
    created_at: datetime
    updated_at: datetime
