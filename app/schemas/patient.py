from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
        min_length=1, max_length=500,
        description="Opaque encrypted-vault reference only; never a raw identity number or image.",
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
    id: UUID
    full_name: str
    relationship: str
    phone_number: str
    email: str | None
    can_be_contacted: bool


class PatientRegistrationRead(BaseModel):
    patient: PatientRead
    profile: PatientRegistrationProfileRead | None
    identity_documents: list[PatientIdentityDocumentRead]
    next_of_kin: list[PatientNextOfKinRead]


class PatientDuplicateCaseReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["not_duplicate", "confirmed_duplicate", "closed"]
    review_note: str = Field(min_length=3, max_length=1000)


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
    reason: str = Field(min_length=3, max_length=1000)


class PatientDuplicateCandidateRead(BaseModel):
    case: PatientDuplicateCaseRead
    candidate: PatientRead
