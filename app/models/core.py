import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)


class Hospital(TimestampMixin, Base):
    __tablename__ = "hospitals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    facility_code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    ownership_type: Mapped[str] = mapped_column(String(24), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), default="KE", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)


class Department(TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("hospital_id", "code", name="uq_department_hospital_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Role(TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("hospital_id", "name", name="uq_role_hospital_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class HospitalMembership(TimestampMixin, Base):
    __tablename__ = "hospital_memberships"
    __table_args__ = (UniqueConstraint("hospital_id", "user_id", name="uq_membership_hospital_user"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"))
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)
    professional_registration: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)


class Patient(TimestampMixin, Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("hospital_id", "medical_record_number", name="uq_patient_hospital_mrn"),
        UniqueConstraint("hospital_id", "id", name="uq_patient_hospital_id_id"),
        Index("ix_patient_hospital_name_dob", "hospital_id", "family_name", "date_of_birth"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False, index=True)
    medical_record_number: Mapped[str] = mapped_column(String(80), nullable=False)
    given_name: Mapped[str] = mapped_column(String(120), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(120))
    preferred_name: Mapped[str | None] = mapped_column(String(120))
    family_name: Mapped[str] = mapped_column(String(120), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    administrative_sex: Mapped[str | None] = mapped_column(String(24))
    nationality: Mapped[str | None] = mapped_column(String(2))
    phone_number: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)


class Encounter(TimestampMixin, Base):
    __tablename__ = "encounters"
    __table_args__ = (Index("ix_encounter_hospital_patient", "hospital_id", "patient_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id"))
    encounter_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="in_progress", nullable=False)
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PatientConsent(TimestampMixin, Base):
    __tablename__ = "patient_consents"
    __table_args__ = (
        Index("ix_consent_hospital_patient_status", "hospital_id", "patient_id", "status"),
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_patient_consent_patient_tenant",
        ),
        CheckConstraint(
            "basis_code IS NULL OR basis_code IN "
            "('patient_consent', 'guardian_consent', 'healthcare_provision', "
            "'vital_interests', 'legal_requirement', 'other_lawful_basis')",
            name="ck_patient_consent_basis_code",
        ),
        CheckConstraint(
            "consent_method IS NULL OR consent_method IN "
            "('written', 'electronic', 'verbal', 'guardian', 'not_applicable')",
            name="ck_patient_consent_method",
        ),
        CheckConstraint(
            "decision_reason_code IS NULL OR decision_reason_code IN "
            "('evidence_confirmed', 'patient_declined', 'guardian_declined', "
            "'withdrawn_by_patient', 'lawful_basis_ended', 'other')",
            name="ck_patient_consent_reason",
        ),
        CheckConstraint(
            "consent_method IS NULL OR "
            "(basis_code = 'patient_consent' AND consent_method IN ('written', 'electronic', 'verbal')) OR "
            "(basis_code = 'guardian_consent' AND consent_method = 'guardian') OR "
            "(basis_code IN ('healthcare_provision', 'vital_interests', 'legal_requirement', 'other_lawful_basis') "
            "AND consent_method = 'not_applicable')",
            name="ck_patient_consent_method_basis",
        ),
        CheckConstraint(
            "evidence_reference IS NULL OR evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'",
            name="ck_patient_consent_evidence_reference",
        ),
        CheckConstraint(
            "basis_code IS NULL OR "
            "(status = 'pending' AND requested_by_user_id IS NOT NULL AND recorded_by_user_id IS NULL "
            "AND evidence_reference IS NULL AND consent_method IS NULL AND granted_at IS NULL "
            "AND withdrawn_at IS NULL AND withdrawn_by_user_id IS NULL AND decision_reason_code IS NULL) OR "
            "(status = 'granted' AND requested_by_user_id IS NOT NULL AND recorded_by_user_id IS NOT NULL "
            "AND evidence_reference IS NOT NULL AND consent_method IS NOT NULL AND granted_at IS NOT NULL "
            "AND withdrawn_at IS NULL AND withdrawn_by_user_id IS NULL AND decision_reason_code = 'evidence_confirmed') OR "
            "(status = 'rejected' AND requested_by_user_id IS NOT NULL AND recorded_by_user_id IS NOT NULL "
            "AND decision_reason_code IN ('patient_declined', 'guardian_declined', 'other') "
            "AND consent_method IS NULL AND evidence_reference IS NULL AND granted_at IS NULL "
            "AND withdrawn_at IS NULL AND withdrawn_by_user_id IS NULL) OR "
            "(status = 'withdrawn' AND requested_by_user_id IS NOT NULL AND recorded_by_user_id IS NOT NULL "
            "AND evidence_reference IS NOT NULL AND consent_method IS NOT NULL AND granted_at IS NOT NULL "
            "AND withdrawn_by_user_id IS NOT NULL AND withdrawn_at IS NOT NULL "
            "AND decision_reason_code IN ('withdrawn_by_patient', 'lawful_basis_ended', 'other'))",
            name="ck_patient_consent_decision_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(240), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    basis_code: Mapped[str | None] = mapped_column(String(32))
    consent_method: Mapped[str | None] = mapped_column(String(24))
    evidence_reference: Mapped[str | None] = mapped_column(String(80))
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    withdrawn_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decision_reason_code: Mapped[str | None] = mapped_column(String(40))
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_hospital_time", "hospital_id", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
