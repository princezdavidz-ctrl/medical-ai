from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


_ALLOWED_SCOPES = {"profile", "encounters", "lab_results", "medications", "invoices", "consents"}


class PatientPortalLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    portal_user_id: UUID
    relationship_type: str = Field(default="self", pattern="^(self|parent_guardian|caregiver|legal_representative)$")
    access_scope: list[str] = Field(default_factory=lambda: ["profile", "encounters", "lab_results", "medications", "invoices", "consents"], min_length=1)
    authority_reference: str | None = Field(default=None, max_length=160)
    expires_at: datetime | None = None


class PatientPortalLinkVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verification_method: str = Field(pattern="^(in_person|identity_document|verified_email|verified_phone|guardian_document|court_order)$")
    evidence_reference: str = Field(pattern="^vault://[0-9a-fA-F-]{36}$")


class PatientPortalLinkRevocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=1000)


class PatientPortalLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    patient_id: UUID
    portal_user_id: UUID
    relationship_type: str
    access_scope: list[str]
    authority_reference: str | None
    expires_at: datetime | None
    status: str
    verification_method: str | None
    evidence_reference: str | None
    requested_by_user_id: UUID
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    revoked_by_user_id: UUID | None
    revoked_at: datetime | None
    revocation_reason: str | None
    created_at: datetime


class PatientPortalPatientRead(BaseModel):
    patient_id: UUID
    medical_record_number: str
    given_name: str
    middle_name: str | None
    preferred_name: str | None
    family_name: str
    date_of_birth: date | None
    administrative_sex: str | None
    phone_number: str | None
    relationship_type: str
    access_scope: list[str]


class PatientPortalEncounterRead(BaseModel):
    id: UUID
    encounter_type: str
    status: str
    chief_complaint: str | None
    started_at: datetime
    ended_at: datetime | None


class PatientPortalLabResultRead(BaseModel):
    id: UUID
    specimen_accession_number: str
    specimen_type: str
    value_text: str | None
    value_numeric: float | None
    unit: str | None
    abnormality: str
    critical_flag: bool
    interpretation_note: str | None
    entered_at: datetime


class PatientPortalMedicationRead(BaseModel):
    id: UUID
    medication_name: str
    strength: str
    dose_text: str
    route: str
    frequency_text: str
    duration_days: int | None
    quantity_prescribed: float
    quantity_unit: str
    instructions: str | None
    status: str
    ordered_at: datetime


class PatientPortalInvoiceRead(BaseModel):
    id: UUID
    invoice_number: str
    currency: str
    subtotal_total: float
    amount_paid_total: float
    balance_due: float
    status: str
    issued_at: datetime | None
    created_at: datetime


class PatientPortalConsentRead(BaseModel):
    id: UUID
    purpose: str
    scope: dict
    status: str
    basis_code: str | None
    consent_method: str | None
    granted_at: datetime | None
    expires_at: datetime | None
    withdrawn_at: datetime | None


class PatientTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hospital_id: UUID
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=256)
