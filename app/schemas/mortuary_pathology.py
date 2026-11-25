from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class MortuaryCaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    encounter_id: UUID | None = None
    case_number: str = Field(min_length=2, max_length=80)
    body_reference: str = Field(min_length=2, max_length=100)
    death_occurred_at: datetime
    death_certification_reference: str | None = Field(default=None, max_length=160)
    storage_location: str = Field(min_length=2, max_length=180)
    legal_hold: bool = False


class MortuaryCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    encounter_id: UUID | None
    case_number: str
    body_reference: str
    death_occurred_at: datetime
    death_certification_reference: str | None
    received_at: datetime
    received_by_user_id: UUID
    storage_location: str
    status: str
    legal_hold: bool
    released_to_name: str | None
    released_to_identity_reference: str | None
    released_by_user_id: UUID | None
    released_at: datetime | None
    created_at: datetime


class MortuaryAuthorizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authority_type: str = Field(pattern="^(next_of_kin_consent|court_order|coroner_directive|public_health_order|other_lawful_basis)$")
    authority_reference: str = Field(min_length=2, max_length=160)
    evidence_reference: str | None = Field(default=None, pattern="^vault://[0-9a-fA-F-]{36}$")


class MortuaryAuthorizationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(verified|rejected)$")
    evidence_reference: str | None = Field(default=None, pattern="^vault://[0-9a-fA-F-]{36}$")


class MortuaryMovementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movement_type: str = Field(pattern="^(stored|relocated|release_pending|retained)$")
    to_location: str = Field(min_length=2, max_length=180)
    note: str | None = Field(default=None, max_length=1000)


class MortuaryPropertyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_description: str = Field(min_length=2, max_length=500)
    property_reference: str | None = Field(default=None, max_length=120)
    sealed: bool = False


class MortuaryPropertyRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(released|retained|sealed)$")
    released_to_name: str | None = Field(default=None, min_length=2, max_length=180)


class MortuaryRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")
    released_to_name: str = Field(min_length=2, max_length=180)
    identity_reference: str = Field(min_length=2, max_length=160)


class PathologyCaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    encounter_id: UUID | None = None
    case_number: str = Field(min_length=2, max_length=80)
    case_type: str = Field(pattern="^(biopsy|surgical|autopsy|forensic)$")
    clinical_indication: str = Field(min_length=3, max_length=5000)
    order_reference: str | None = Field(default=None, max_length=160)
    authority_type: str | None = Field(default=None, pattern="^(patient_consent|next_of_kin_consent|court_order|coroner_directive|public_health_order|other_lawful_basis)$")
    authority_reference: str | None = Field(default=None, max_length=160)


class PathologyCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    encounter_id: UUID | None
    case_number: str
    case_type: str
    clinical_indication: str
    order_reference: str | None
    authority_type: str | None
    authority_reference: str | None
    authority_verified_by_user_id: UUID | None
    authority_verified_at: datetime | None
    status: str
    assigned_pathologist_user_id: UUID | None
    opened_by_user_id: UUID
    created_at: datetime


class PathologyAuthorityVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: bool
    evidence_reference: str | None = Field(default=None, pattern="^vault://[0-9a-fA-F-]{36}$")


class PathologySpecimenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accession_number: str = Field(min_length=2, max_length=100)
    specimen_type: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=3, max_length=1000)
    specimen_condition: str = Field(default="acceptable", pattern="^(acceptable|damaged|leaking|unlabelled|other)$")
    collected_at: datetime | None = None


class PathologySpecimenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pathology_case_id: UUID
    accession_number: str
    specimen_type: str
    description: str
    specimen_condition: str
    status: str
    collected_at: datetime | None
    received_at: datetime | None
    received_by_user_id: UUID | None
    created_at: datetime


class PathologySpecimenStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(received|processing|processed|archived|rejected)$")


class PathologyReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: str = Field(min_length=3, max_length=12000)
    interpretation: str | None = Field(default=None, max_length=8000)
    conclusion: str = Field(min_length=3, max_length=5000)


class PathologyReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pathology_case_id: UUID
    version: int
    findings: str
    interpretation: str | None
    conclusion: str
    status: str
    authored_by_user_id: UUID
    signed_by_user_id: UUID | None
    signed_at: datetime | None
    created_at: datetime
