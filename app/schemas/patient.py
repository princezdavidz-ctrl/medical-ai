from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PatientRegistrationProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = Field(default=None, max_length=320)
    alternate_phone_number: str | None = Field(default=None, max_length=40)
    address_line_1: str | None = Field(default=None, max_length=240)
    address_line_2: str | None = Field(default=None, max_length=240)
    county: str | None = Field(default=None, max_length=100)
    sub_county: str | None = Field(default=None, max_length=100)
    country_code: str = Field(default="KE", pattern="^[A-Z]{2}$")
    postal_code: str | None = Field(default=None, max_length=24)
    preferred_language: str | None = Field(default=None, max_length=60)
    registration_source: Literal["walk_in", "referral", "transfer", "portal", "import"] = "walk_in"


class PatientIdentityDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: Literal[
        "national_id", "passport", "birth_certificate", "alien_id", "refugee_document", "other"
    ]
    issuing_country: str = Field(default="KE", pattern="^[A-Z]{2}$")
    encrypted_identifier_ref: str = Field(
        min_length=44, max_length=44, pattern="^vault://[0-9a-fA-F-]{36}$",
        description="Opaque vault:// UUID reference only; never a raw identity number or image.",
    )
    expires_at: datetime | None = None


class PatientNextOfKinCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=200)
    relationship: str = Field(min_length=1, max_length=80)
    phone_number: str = Field(min_length=1, max_length=40)
    email: str | None = Field(default=None, max_length=320)
    can_be_contacted: bool = False
    permission_basis: Literal[
        "patient_consent", "legal_guardian_consent", "other_lawful_basis"
    ] | None = None

    @model_validator(mode="after")
    def validate_contact_permission(self):
        if self.can_be_contacted and self.permission_basis is None:
            raise ValueError("permission_basis_required_when_contact_is_allowed")
        if not self.can_be_contacted and self.permission_basis is not None:
            raise ValueError("permission_basis_requires_contact_permission")
        return self


class PatientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medical_record_number: str = Field(min_length=1, max_length=80)
    given_name: str = Field(min_length=1, max_length=120)
    middle_name: str | None = Field(default=None, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    family_name: str = Field(min_length=1, max_length=120)
    date_of_birth: date | None = None
    administrative_sex: str | None = Field(default=None, max_length=24)
    nationality: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    phone_number: str | None = Field(default=None, max_length=40)
    profile: PatientRegistrationProfileCreate | None = None
    identity_documents: list[PatientIdentityDocumentCreate] = Field(default_factory=list, max_length=5)
    next_of_kin: list[PatientNextOfKinCreate] = Field(default_factory=list, max_length=5)

    @field_validator("medical_record_number", "given_name", "family_name", mode="before")
    @classmethod
    def trim_required_identity_fields(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("middle_name", "preferred_name", "phone_number", mode="before")
    @classmethod
    def trim_optional_identity_fields(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("date_of_birth")
    @classmethod
    def reject_future_birth_dates(cls, value):
        if value is not None and value > date.today():
            raise ValueError("date_of_birth_cannot_be_in_the_future")
        return value


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    medical_record_number: str
    given_name: str
    middle_name: str | None
    preferred_name: str | None
    family_name: str
    date_of_birth: date | None
    administrative_sex: str | None
    nationality: str | None
    phone_number: str | None
    status: str
    created_at: datetime


class PatientRegistrationProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str | None
    alternate_phone_number: str | None
    address_line_1: str | None
    address_line_2: str | None
    county: str | None
    sub_county: str | None
    country_code: str
    postal_code: str | None
    preferred_language: str | None
    registration_source: str
    registration_completed_at: datetime | None


class PatientIdentityDocumentRead(BaseModel):
    id: UUID
    document_type: str
    issuing_country: str
    verification_status: str
    verification_reason_code: str | None
    expires_at: datetime | None
    verified_at: datetime | None


class PatientNextOfKinRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    relationship: str
    phone_number: str
    email: str | None
    can_be_contacted: bool
    permission_basis: str | None


class PatientRegistrationRead(BaseModel):
    patient: PatientRead
    profile: PatientRegistrationProfileRead | None
    identity_documents: list[PatientIdentityDocumentRead]
    next_of_kin: list[PatientNextOfKinRead]


class PatientDuplicateCaseReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["not_duplicate", "confirmed_duplicate", "closed"]
    review_note: str = Field(min_length=3, max_length=1000)

    @field_validator("review_note")
    @classmethod
    def trim_review_note(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("duplicate_review_note_too_short")
        return value


class PatientDuplicateCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    candidate_patient_id: UUID
    match_score: int
    matching_signals_json: dict
    status: str
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime


class PatientIdentityDocumentVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_status: Literal["verified", "rejected"]
    reason_code: Literal[
        "verified_document", "expired_document", "unreadable_document",
        "identity_mismatch", "unsupported_document",
    ]

    @model_validator(mode="after")
    def validate_verification_reason(self):
        if self.verification_status == "verified" and self.reason_code != "verified_document":
            raise ValueError("verified_document_reason_required")
        if self.verification_status == "rejected" and self.reason_code == "verified_document":
            raise ValueError("rejected_document_requires_rejection_reason")
        return self


class PatientRegistrationProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = Field(default=None, max_length=320)
    alternate_phone_number: str | None = Field(default=None, max_length=40)
    address_line_1: str | None = Field(default=None, max_length=240)
    address_line_2: str | None = Field(default=None, max_length=240)
    county: str | None = Field(default=None, max_length=100)
    sub_county: str | None = Field(default=None, max_length=100)
    country_code: str = Field(default="KE", pattern="^[A-Z]{2}$")
    postal_code: str | None = Field(default=None, max_length=24)
    preferred_language: str | None = Field(default=None, max_length=60)


class PatientStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "inactive", "deceased"]
    reason_code: Literal[
        "administrative_correction", "patient_request", "deceased_confirmation", "other",
    ]

    @model_validator(mode="after")
    def validate_status_reason(self):
        if self.status == "deceased" and self.reason_code != "deceased_confirmation":
            raise ValueError("deceased_status_requires_deceased_confirmation")
        if self.status != "deceased" and self.reason_code == "deceased_confirmation":
            raise ValueError("deceased_confirmation_only_valid_for_deceased_status")
        return self


class PatientDuplicateCandidateRead(BaseModel):
    case: PatientDuplicateCaseRead
    candidate: PatientRead


class PatientDemographicsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    given_name: str | None = Field(default=None, min_length=1, max_length=120)
    middle_name: str | None = Field(default=None, max_length=120)
    preferred_name: str | None = Field(default=None, max_length=120)
    family_name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    administrative_sex: str | None = Field(default=None, max_length=24)
    nationality: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    phone_number: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def require_at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("at_least_one_demographic_field_required")
        if "given_name" in self.model_fields_set and self.given_name is None:
            raise ValueError("given_name_cannot_be_null")
        if "family_name" in self.model_fields_set and self.family_name is None:
            raise ValueError("family_name_cannot_be_null")
        return self

    @field_validator("given_name", "family_name", mode="before")
    @classmethod
    def trim_required_names(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("middle_name", "preferred_name", "phone_number", mode="before")
    @classmethod
    def trim_optional_names(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("date_of_birth")
    @classmethod
    def reject_future_birth_dates(cls, value):
        if value is not None and value > date.today():
            raise ValueError("date_of_birth_cannot_be_in_the_future")
        return value


class PatientConsentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: Literal[
        "care_delivery", "care_coordination", "referral", "billing",
        "insurance_claim", "patient_portal", "record_sharing", "other",
    ]
    data_categories: list[Literal[
        "demographics", "contact_details", "clinical_records", "lab_results",
        "imaging", "medications", "billing", "insurance", "other",
    ]] = Field(min_length=1, max_length=20)
    permitted_uses: list[Literal[
        "care_delivery", "care_coordination", "referral", "billing",
        "insurance_claim", "patient_portal", "other_lawful_use",
    ]] = Field(min_length=1, max_length=20)
    basis_code: Literal[
        "patient_consent", "guardian_consent", "healthcare_provision",
        "vital_interests", "legal_requirement", "other_lawful_basis",
    ]
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def require_future_expiry(cls, value):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("consent_expiry_must_include_timezone")
            if value <= datetime.now(timezone.utc):
                raise ValueError("consent_expiry_must_be_in_future")
        return value

    @model_validator(mode="after")
    def require_unique_scope_values(self):
        if len(set(self.data_categories)) != len(self.data_categories):
            raise ValueError("duplicate_data_category")
        if len(set(self.permitted_uses)) != len(self.permitted_uses):
            raise ValueError("duplicate_permitted_use")
        required_use = "other_lawful_use" if self.purpose == "other" else self.purpose
        if required_use not in self.permitted_uses:
            raise ValueError("consent_scope_must_include_declared_purpose")
        return self


class PatientConsentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["grant", "reject", "withdraw"]
    consent_method: Literal[
        "written", "electronic", "verbal", "guardian", "not_applicable",
    ] | None = None
    evidence_reference: str | None = Field(
        default=None,
        min_length=44,
        max_length=44,
        pattern="^vault://[0-9a-fA-F-]{36}$",
    )
    reason_code: Literal[
        "evidence_confirmed", "patient_declined", "guardian_declined",
        "withdrawn_by_patient", "lawful_basis_ended", "other",
    ]

    @model_validator(mode="after")
    def validate_decision_fields(self):
        if self.decision == "grant":
            if self.evidence_reference is None or self.consent_method is None:
                raise ValueError("grant_requires_evidence_and_consent_method")
            if self.reason_code != "evidence_confirmed":
                raise ValueError("grant_requires_evidence_confirmed_reason")
        elif self.decision == "reject":
            if self.reason_code not in {"patient_declined", "guardian_declined", "other"}:
                raise ValueError("invalid_rejection_reason")
            if self.consent_method is not None or self.evidence_reference is not None:
                raise ValueError("rejection_must_not_include_grant_evidence")
        elif self.decision == "withdraw":
            if self.reason_code not in {"withdrawn_by_patient", "lawful_basis_ended", "other"}:
                raise ValueError("invalid_withdrawal_reason")
            if self.consent_method is not None or self.evidence_reference is not None:
                raise ValueError("withdrawal_must_not_include_grant_evidence")
        return self


class PatientConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purpose: str
    scope: dict
    status: str
    basis_code: str | None
    consent_method: str | None
    requested_by_user_id: UUID | None
    recorded_by_user_id: UUID | None
    withdrawn_by_user_id: UUID | None
    decision_reason_code: str | None
    granted_at: datetime | None
    expires_at: datetime | None
    withdrawn_at: datetime | None
    effective_status: str
