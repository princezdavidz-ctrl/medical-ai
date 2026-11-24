import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MedicationDefinition(Base):
    __tablename__ = "medication_definitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_medication_definition_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_medication_definition_hospital_id"),
        UniqueConstraint("hospital_id", "code", name="uq_medication_definition_code"),
        CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_medication_definition_status"),
        CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'active' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NOT NULL AND retired_at IS NOT NULL "
            "AND retirement_reason IS NOT NULL AND length(trim(retirement_reason)) >= 3)",
            name="ck_medication_definition_approval_state",
        ),
        CheckConstraint(
            "approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id",
            name="ck_medication_definition_two_person",
        ),
        CheckConstraint(
            "length(trim(code)) >= 2 AND length(trim(generic_name)) >= 2 "
            "AND length(trim(active_ingredient)) >= 2 AND length(trim(strength_label)) >= 1 "
            "AND length(trim(dosage_form)) >= 2",
            name="ck_medication_definition_text",
        ),
        Index("ix_medication_definition_department_status", "hospital_id", "department_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    generic_name: Mapped[str] = mapped_column(String(180), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(180))
    active_ingredient: Mapped[str] = mapped_column(String(180), nullable=False)
    strength_label: Mapped[str] = mapped_column(String(100), nullable=False)
    dosage_form: Mapped[str] = mapped_column(String(100), nullable=False)
    default_route: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirement_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MedicationOrder(Base):
    __tablename__ = "medication_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_medication_order_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_medication_order_encounter_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "ordering_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_medication_order_ordering_department",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "pharmacy_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_medication_order_pharmacy_department",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "medication_definition_id"],
            ["medication_definitions.hospital_id", "medication_definitions.id"],
            name="fk_medication_order_definition",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_medication_order_hospital_id"),
        CheckConstraint(
            "status IN ('pending_pharmacy_review', 'approved_for_dispense', 'on_hold', "
            "'rejected', 'partially_dispensed', 'dispensed', 'cancelled')",
            name="ck_medication_order_status",
        ),
        CheckConstraint(
            "route IN ('oral', 'topical', 'inhalation', 'intravenous', 'intramuscular', "
            "'subcutaneous', 'rectal', 'ophthalmic', 'otic', 'nasal', 'transdermal', 'other')",
            name="ck_medication_order_route",
        ),
        CheckConstraint("quantity_prescribed > 0", name="ck_medication_order_quantity"),
        CheckConstraint("duration_days IS NULL OR duration_days BETWEEN 1 AND 3650", name="ck_medication_order_duration"),
        CheckConstraint("refills BETWEEN 0 AND 12", name="ck_medication_order_refills"),
        CheckConstraint("quantity_dispensed_total >= 0 AND quantity_dispensed_total <= quantity_prescribed", name="ck_medication_order_dispensed_quantity"),
        CheckConstraint(
            "(status IN ('partially_dispensed', 'dispensed') AND quantity_dispensed_total > 0) OR "
            "(status NOT IN ('partially_dispensed', 'dispensed') AND quantity_dispensed_total = 0)",
            name="ck_medication_order_dispense_state",
        ),
        CheckConstraint(
            "status != 'dispensed' OR quantity_dispensed_total = quantity_prescribed",
            name="ck_medication_order_fully_dispensed",
        ),
        CheckConstraint(
            "status != 'partially_dispensed' OR quantity_dispensed_total < quantity_prescribed",
            name="ck_medication_order_partial_dispense",
        ),
        CheckConstraint(
            "status != 'cancelled' OR (cancelled_at IS NOT NULL AND cancelled_by_user_id IS NOT NULL "
            "AND cancellation_reason IS NOT NULL AND length(trim(cancellation_reason)) >= 3)",
            name="ck_medication_order_cancellation",
        ),
        CheckConstraint(
            "status = 'cancelled' OR (cancelled_at IS NULL AND cancelled_by_user_id IS NULL AND cancellation_reason IS NULL)",
            name="ck_medication_order_no_unexpected_cancellation",
        ),
        CheckConstraint(
            "length(trim(dose_text)) >= 1 AND length(trim(frequency_text)) >= 1 "
            "AND length(trim(quantity_unit)) >= 1 AND length(trim(indication)) >= 3",
            name="ck_medication_order_prescription_text",
        ),
        Index("ix_medication_order_patient_encounter", "hospital_id", "patient_id", "encounter_id"),
        Index("ix_medication_order_pharmacy_queue", "hospital_id", "pharmacy_department_id", "status", "ordered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ordering_department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pharmacy_department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    medication_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    prescribed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    dose_text: Mapped[str] = mapped_column(String(160), nullable=False)
    route: Mapped[str] = mapped_column(String(32), nullable=False)
    frequency_text: Mapped[str] = mapped_column(String(160), nullable=False)
    duration_days: Mapped[int | None] = mapped_column()
    quantity_prescribed: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(40), nullable=False)
    refills: Mapped[int] = mapped_column(nullable=False, default=0)
    indication: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_pharmacy_review")
    quantity_dispensed_total: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)


class MedicationOrderReviewEvent(Base):
    __tablename__ = "medication_order_review_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "order_id"],
            ["medication_orders.hospital_id", "medication_orders.id"],
            name="fk_medication_review_order",
        ),
        CheckConstraint("decision IN ('approved', 'on_hold', 'rejected')", name="ck_medication_review_decision"),
        CheckConstraint("length(trim(review_note)) >= 3", name="ck_medication_review_note"),
        Index("ix_medication_review_order_time", "hospital_id", "order_id", "reviewed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    review_note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MedicationDispense(Base):
    __tablename__ = "medication_dispenses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "order_id"],
            ["medication_orders.hospital_id", "medication_orders.id"],
            name="fk_medication_dispense_order",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_medication_dispense_hospital_id"),
        CheckConstraint("quantity_dispensed > 0", name="ck_medication_dispense_quantity"),
        CheckConstraint("length(trim(quantity_unit)) >= 1", name="ck_medication_dispense_unit"),
        Index("ix_medication_dispense_order_time", "hospital_id", "order_id", "dispensed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dispensed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    quantity_dispensed: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(40), nullable=False)
    batch_reference: Mapped[str | None] = mapped_column(String(120))
    dispense_note: Mapped[str | None] = mapped_column(Text)
    dispensed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
