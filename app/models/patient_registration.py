import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    JSON, SmallInteger, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.core import TimestampMixin


class PatientRegistrationProfile(TimestampMixin, Base):
    """Additional demographic/contact details, scoped to one hospital patient record."""

    __tablename__ = "patient_registration_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_patient_registration_profile_patient",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "registration_source IN ('walk_in', 'referral', 'transfer', 'portal', 'import')",
            name="ck_patient_registration_source",
        ),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("hospitals.id"), primary_key=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320))
    alternate_phone_number: Mapped[str | None] = mapped_column(String(40))
    address_line_1: Mapped[str | None] = mapped_column(String(240))
    address_line_2: Mapped[str | None] = mapped_column(String(240))
    county: Mapped[str | None] = mapped_column(String(100))
    sub_county: Mapped[str | None] = mapped_column(String(100))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="KE")
    postal_code: Mapped[str | None] = mapped_column(String(24))
    preferred_language: Mapped[str | None] = mapped_column(String(60))
    registration_source: Mapped[str] = mapped_column(String(24), nullable=False, default="walk_in")
    registered_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    registration_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PatientIdentityDocument(Base):
    """Identity metadata; raw document numbers/images must remain in an encrypted vault."""

    __tablename__ = "patient_identity_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_patient_identity_document_patient",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "document_type IN ('national_id', 'passport', 'birth_certificate', 'alien_id', "
            "'refugee_document', 'other')",
            name="ck_patient_identity_document_type",
        ),
        CheckConstraint(
            "verification_status IN ('pending', 'verified', 'rejected')",
            name="ck_patient_identity_document_status",
        ),
        CheckConstraint(
            "verification_reason_code IS NULL OR verification_reason_code IN "
            "('verified_document', 'expired_document', 'unreadable_document', 'identity_mismatch', 'unsupported_document')",
            name="ck_patient_identity_document_reason",
        ),
        CheckConstraint(
            "(verification_status = 'pending' AND verification_reason_code IS NULL "
            "AND verified_by_user_id IS NULL AND verified_at IS NULL) OR "
            "(verification_status = 'verified' AND verification_reason_code = 'verified_document' "
            "AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL) OR "
            "(verification_status = 'rejected' AND verification_reason_code IN "
            "('expired_document', 'unreadable_document', 'identity_mismatch', 'unsupported_document') "
            "AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_patient_identity_document_reviewed",
        ),
        CheckConstraint(
            "identifier_fingerprint_hmac IS NULL OR length(identifier_fingerprint_hmac) = 64",
            name="ck_patient_identity_fingerprint_length",
        ),
        Index("ix_patient_identity_hospital_patient", "hospital_id", "patient_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("hospitals.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    issuing_country: Mapped[str] = mapped_column(String(2), nullable=False, default="KE")
    encrypted_identifier_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    identifier_fingerprint_hmac: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    verification_reason_code: Mapped[str | None] = mapped_column(String(40))
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PatientNextOfKin(Base):
    """Patient-designated contact; permission to contact is explicit and false by default."""

    __tablename__ = "patient_next_of_kin"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_patient_next_of_kin_patient",
            ondelete="CASCADE",
        ),
        Index("ix_patient_next_of_kin_hospital_patient", "hospital_id", "patient_id"),
        CheckConstraint(
            "(permission_basis IS NULL OR permission_basis IN ('patient_consent', 'legal_guardian_consent', 'other_lawful_basis')) "
            "AND (can_be_contacted = false OR (permission_basis IS NOT NULL AND permission_recorded_at IS NOT NULL))",
            name="ck_patient_next_of_kin_permission_basis",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("hospitals.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    relationship: Mapped[str] = mapped_column(String(80), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    can_be_contacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    permission_basis: Mapped[str | None] = mapped_column(String(32))
    permission_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PatientDuplicateCase(Base):
    """Human-reviewed possible duplicate; this table never merges patient records."""

    __tablename__ = "patient_duplicate_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_patient_duplicate_case_patient",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "candidate_patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_patient_duplicate_case_candidate",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "hospital_id", "patient_id", "candidate_patient_id",
            name="uq_patient_duplicate_case_pair",
        ),
        CheckConstraint("patient_id <> candidate_patient_id", name="ck_patient_duplicate_distinct"),
        CheckConstraint("match_score BETWEEN 0 AND 100", name="ck_patient_duplicate_score"),
        CheckConstraint(
            "status IN ('pending', 'not_duplicate', 'confirmed_duplicate', 'closed')",
            name="ck_patient_duplicate_status",
        ),
        CheckConstraint(
            "(status = 'pending' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND review_note IS NULL) OR "
            "(status <> 'pending' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND review_note IS NOT NULL)",
            name="ck_patient_duplicate_reviewed",
        ),
        Index("ix_patient_duplicate_review_queue", "hospital_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("hospitals.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    candidate_patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    match_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    matching_signals_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
