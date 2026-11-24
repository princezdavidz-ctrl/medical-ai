import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InsurerDefinition(Base):
    __tablename__ = "insurer_definitions"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_insurer_definition_hospital_id"),
        UniqueConstraint("hospital_id", "code", name="uq_insurer_definition_code"),
        CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_insurer_definition_status"),
        CheckConstraint("approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id", name="ck_insurer_definition_two_person"),
        CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'active' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL AND retired_by_user_id IS NOT NULL AND retired_at IS NOT NULL AND retirement_reason IS NOT NULL AND length(trim(retirement_reason)) >= 3)",
            name="ck_insurer_definition_lifecycle",
        ),
        CheckConstraint("insurer_type IN ('kenya_sha', 'private', 'employer', 'other')", name="ck_insurer_definition_type"),
        Index("ix_insurer_definition_status", "hospital_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    insurer_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirement_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PatientCoverage(Base):
    __tablename__ = "patient_coverages"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_patient_coverage_patient"),
        ForeignKeyConstraint(["hospital_id", "insurer_definition_id"], ["insurer_definitions.hospital_id", "insurer_definitions.id"], name="fk_patient_coverage_insurer"),
        UniqueConstraint("hospital_id", "id", name="uq_patient_coverage_hospital_id"),
        CheckConstraint("status IN ('reported', 'verified', 'suspended', 'expired', 'cancelled')", name="ck_patient_coverage_status"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_patient_coverage_dates"),
        Index("ix_patient_coverage_patient", "hospital_id", "patient_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    insurer_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    member_number: Mapped[str] = mapped_column(String(120), nullable=False)
    policy_number: Mapped[str | None] = mapped_column(String(120))
    principal_member_name: Mapped[str | None] = mapped_column(String(180))
    relationship_to_principal: Mapped[str | None] = mapped_column(String(40))
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="reported")
    verification_reference: Mapped[str | None] = mapped_column(String(160))
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InsuranceClaim(Base):
    __tablename__ = "insurance_claims"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_insurance_claim_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_insurance_claim_encounter"),
        ForeignKeyConstraint(["hospital_id", "coverage_id"], ["patient_coverages.hospital_id", "patient_coverages.id"], name="fk_insurance_claim_coverage"),
        ForeignKeyConstraint(["hospital_id", "invoice_id"], ["invoices.hospital_id", "invoices.id"], name="fk_insurance_claim_invoice"),
        UniqueConstraint("hospital_id", "id", name="uq_insurance_claim_hospital_id"),
        UniqueConstraint("hospital_id", "claim_number", name="uq_insurance_claim_number"),
        UniqueConstraint("hospital_id", "external_claim_reference", name="uq_insurance_claim_external_reference"),
        CheckConstraint("status IN ('draft', 'submitted', 'accepted', 'partially_approved', 'rejected', 'partially_paid', 'paid', 'closed')", name="ck_insurance_claim_status"),
        CheckConstraint("claimed_amount > 0 AND approved_amount >= 0 AND paid_amount >= 0", name="ck_insurance_claim_amounts_nonnegative"),
        CheckConstraint("approved_amount <= claimed_amount AND paid_amount <= approved_amount", name="ck_insurance_claim_amount_limits"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_insurance_claim_currency"),
        CheckConstraint("status != 'draft' OR (submitted_at IS NULL AND adjudicated_at IS NULL)", name="ck_insurance_claim_draft_state"),
        Index("ix_insurance_claim_queue", "hospital_id", "status", "created_at"),
        Index("ix_insurance_claim_patient", "hospital_id", "patient_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    coverage_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    claim_number: Mapped[str] = mapped_column(String(80), nullable=False)
    external_claim_reference: Mapped[str | None] = mapped_column(String(160))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    claimed_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    approved_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    submission_note: Mapped[str | None] = mapped_column(Text)
    adjudication_note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    adjudicated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    adjudicated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_payment_recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    last_payment_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InsuranceClaimEvent(Base):
    __tablename__ = "insurance_claim_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "claim_id"], ["insurance_claims.hospital_id", "insurance_claims.id"], name="fk_insurance_claim_event_claim"),
        Index("ix_insurance_claim_event_time", "hospital_id", "claim_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    claim_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
