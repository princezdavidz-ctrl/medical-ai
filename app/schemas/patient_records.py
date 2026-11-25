from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RecordCategory = Literal[
    "demographics", "contact_details", "clinical_records", "lab_results",
    "imaging", "medications", "billing", "insurance", "other",
]


class RecordDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    encounter_id: UUID | None = None
    source_module: Literal["opd", "nursing", "inpatient", "emergency", "icu", "surgery", "maternity", "pediatrics", "laboratory", "radiology", "pharmacy", "billing", "insurance", "external", "other"]
    source_record_id: UUID | None = None
    record_type: Literal["clinical_note", "discharge_summary", "lab_report", "imaging_report", "prescription", "referral", "consent", "identity_document", "administrative", "external_record", "other"]
    title: str = Field(min_length=2, max_length=240)
    document_date: datetime
    mime_type: Literal["application/pdf", "image/jpeg", "image/png", "application/dicom", "text/plain", "application/octet-stream"]
    vault_reference: str = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)
    sha256_checksum: str = Field(pattern=r"^[0-9a-fA-F]{64}$", min_length=64, max_length=64)
    version_number: int = Field(default=1, ge=1)
    supersedes_document_id: UUID | None = None

    @field_validator("document_date")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("document_date_must_be_timezone_aware")
        return value

    @field_validator("sha256_checksum")
    @classmethod
    def normalize_checksum(cls, value):
        return value.lower()

    @model_validator(mode="after")
    def version_chain(self):
        if self.version_number == 1 and self.supersedes_document_id is not None:
            raise ValueError("first_version_cannot_supersede_document")
        if self.version_number > 1 and self.supersedes_document_id is None:
            raise ValueError("later_version_requires_superseded_document")
        return self


class RecordDocumentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["verify", "reject"]
    reason: str | None = Field(default=None, min_length=5, max_length=1000)

    @model_validator(mode="after")
    def rejection_reason_required(self):
        if self.decision == "reject" and not self.reason:
            raise ValueError("document_rejection_reason_required")
        return self


class RecordDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    encounter_id: UUID | None
    source_module: str
    source_record_id: UUID | None
    record_type: str
    title: str
    document_date: datetime
    mime_type: str
    vault_reference: str
    sha256_checksum: str
    version_number: int
    supersedes_document_id: UUID | None
    status: str
    rejection_reason: str | None
    created_by_user_id: UUID
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    created_at: datetime


class RecordReleaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    consent_id: UUID
    requester_type: Literal["patient", "legal_representative", "treating_provider", "insurer", "court", "regulator", "other"]
    requester_name: str = Field(min_length=2, max_length=180)
    requester_evidence_reference: str | None = Field(default=None, pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)
    recipient_name: str = Field(min_length=2, max_length=180)
    recipient_type: Literal["hospital", "clinic", "provider", "insurer", "patient", "court", "regulator", "other"]
    recipient_contact: str | None = Field(default=None, max_length=320)
    purpose: Literal["record_sharing", "care_coordination", "referral", "patient_portal", "insurance_claim", "legal_requirement", "other"]
    data_categories: list[RecordCategory] = Field(min_length=1, max_length=9)
    period_start: datetime | None = None
    period_end: datetime | None = None
    request_reason: str = Field(min_length=5, max_length=1000)

    @model_validator(mode="after")
    def validate_request(self):
        if self.requester_type in {"insurer", "court", "regulator", "other"} and not self.requester_evidence_reference:
            raise ValueError("external_requester_evidence_required")
        if len(set(self.data_categories)) != len(self.data_categories):
            raise ValueError("duplicate_record_category")
        for value in (self.period_start, self.period_end):
            if value is not None and value.tzinfo is None:
                raise ValueError("release_period_must_be_timezone_aware")
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError("release_period_end_before_start")
        return self


class RecordReleaseDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, min_length=5, max_length=1000)

    @model_validator(mode="after")
    def rejection_reason_required(self):
        if self.decision == "reject" and not self.reason:
            raise ValueError("release_rejection_reason_required")
        return self


class RecordReleaseComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    release_vault_reference: str = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class RecordReleaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    consent_id: UUID
    requester_user_id: UUID
    requester_type: str
    requester_name: str
    requester_evidence_reference: str | None
    recipient_name: str
    recipient_type: str
    recipient_contact: str | None
    purpose: str
    data_categories: list[str]
    period_start: datetime | None
    period_end: datetime | None
    request_reason: str
    status: str
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    decision_reason: str | None
    released_by_user_id: UUID | None
    released_at: datetime | None
    release_vault_reference: str | None
    created_at: datetime


class RecordAmendmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    document_id: UUID | None = None
    amendment_type: Literal["demographic", "clinical_content", "metadata", "identity"]
    reason: str = Field(min_length=5, max_length=1000)
    supporting_evidence_reference: str | None = Field(default=None, pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class RecordAmendmentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, min_length=5, max_length=1000)

    @model_validator(mode="after")
    def rejection_reason_required(self):
        if self.decision == "reject" and not self.reason:
            raise ValueError("amendment_rejection_reason_required")
        return self


class RecordAmendmentFulfil(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amendment_vault_reference: str = Field(pattern=r"^vault://[0-9a-fA-F-]{36}$", min_length=44, max_length=44)


class RecordAmendmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    document_id: UUID | None
    requested_by_user_id: UUID
    amendment_type: str
    reason: str
    supporting_evidence_reference: str | None
    status: str
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    decision_reason: str | None
    fulfilled_by_user_id: UUID | None
    fulfilled_at: datetime | None
    amendment_vault_reference: str | None
    created_at: datetime
