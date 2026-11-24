import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Numeric, String, Text, UniqueConstraint, Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LaboratoryTestDefinition(Base):
    __tablename__ = "laboratory_test_definitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_lab_test_definition_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_lab_test_definition_hospital_id"),
        UniqueConstraint("hospital_id", "code", name="uq_lab_test_definition_code"),
        CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_lab_test_definition_status"),
        CheckConstraint("length(trim(code)) >= 2 AND length(trim(name)) >= 2 AND length(trim(specimen_type)) >= 2", name="ck_lab_test_definition_text"),
        CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'active' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NOT NULL AND retired_at IS NOT NULL "
            "AND retirement_reason IS NOT NULL AND length(trim(retirement_reason)) >= 3)",
            name="ck_lab_test_definition_approval_state",
        ),
        CheckConstraint(
            "approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id",
            name="ck_lab_test_definition_two_person",
        ),
        Index("ix_lab_test_definition_department_status", "hospital_id", "department_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    specimen_type: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str | None] = mapped_column(String(160))
    result_unit: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirement_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LaboratoryOrder(Base):
    __tablename__ = "laboratory_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_lab_order_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_lab_order_encounter_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "ordering_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_lab_order_ordering_department",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "laboratory_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_lab_order_laboratory_department",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "test_definition_id"],
            ["laboratory_test_definitions.hospital_id", "laboratory_test_definitions.id"],
            name="fk_lab_order_test_definition",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_lab_order_hospital_id"),
        CheckConstraint("status IN ('ordered', 'in_progress', 'completed', 'cancelled')", name="ck_lab_order_status"),
        CheckConstraint("priority IN ('routine', 'urgent', 'stat')", name="ck_lab_order_priority"),
        CheckConstraint("length(trim(clinical_indication)) >= 3", name="ck_lab_order_indication"),
        CheckConstraint(
            "(status = 'cancelled' AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL "
            "AND length(trim(cancellation_reason)) >= 3) OR "
            "(status != 'cancelled' AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL AND cancellation_reason IS NULL)",
            name="ck_lab_order_cancellation_state",
        ),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status != 'completed' AND completed_at IS NULL)",
            name="ck_lab_order_completion_timestamp",
        ),
        Index("ix_lab_order_patient_encounter", "hospital_id", "patient_id", "encounter_id"),
        Index("ix_lab_order_lab_queue", "hospital_id", "laboratory_department_id", "status", "ordered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ordering_department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    laboratory_department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    test_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ordered_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="routine")
    clinical_indication: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ordered")
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)


class LaboratorySpecimen(Base):
    __tablename__ = "laboratory_specimens"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "order_id"],
            ["laboratory_orders.hospital_id", "laboratory_orders.id"],
            name="fk_lab_specimen_order",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_lab_specimen_hospital_id"),
        UniqueConstraint("hospital_id", "accession_number", name="uq_lab_specimen_accession"),
        CheckConstraint(
            "status IN ('collected', 'received', 'processing', 'rejected', 'completed')",
            name="ck_lab_specimen_status",
        ),
        CheckConstraint(
            "length(trim(accession_number)) >= 2 AND length(trim(specimen_type)) >= 2",
            name="ck_lab_specimen_text",
        ),
        CheckConstraint(
            "(status = 'rejected' AND rejected_at IS NOT NULL AND rejection_reason IS NOT NULL "
            "AND length(trim(rejection_reason)) >= 3) OR "
            "(status != 'rejected' AND rejected_at IS NULL AND rejection_reason IS NULL)",
            name="ck_lab_specimen_rejection_state",
        ),
        CheckConstraint(
            "status NOT IN ('received', 'processing', 'completed') OR received_at IS NOT NULL",
            name="ck_lab_specimen_received_state",
        ),
        CheckConstraint(
            "status NOT IN ('processing', 'completed') OR processing_started_at IS NOT NULL",
            name="ck_lab_specimen_processing_state",
        ),
        CheckConstraint(
            "(status = 'collected' AND received_at IS NULL AND processing_started_at IS NULL) OR "
            "(status = 'received' AND received_at IS NOT NULL AND processing_started_at IS NULL) OR "
            "(status = 'processing' AND received_at IS NOT NULL AND processing_started_at IS NOT NULL) OR "
            "(status = 'rejected') OR "
            "(status = 'completed' AND received_at IS NOT NULL AND processing_started_at IS NOT NULL)",
            name="ck_lab_specimen_workflow_timestamps",
        ),
        Index("ix_lab_specimen_order_time", "hospital_id", "order_id", "collected_at"),
        Index(
            "uq_lab_specimen_one_active_per_order",
            "hospital_id", "order_id",
            unique=True,
            postgresql_where=text("status != 'rejected'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(100), nullable=False)
    specimen_type: Mapped[str] = mapped_column(String(100), nullable=False)
    collected_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="collected")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)


class LaboratoryResult(Base):
    __tablename__ = "laboratory_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "specimen_id"],
            ["laboratory_specimens.hospital_id", "laboratory_specimens.id"],
            name="fk_lab_result_specimen",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_lab_result_hospital_id"),
        UniqueConstraint("hospital_id", "specimen_id", name="uq_lab_result_specimen"),
        CheckConstraint(
            "value_text IS NULL OR length(trim(value_text)) >= 1",
            name="ck_lab_result_text_value",
        ),
        CheckConstraint(
            "(value_text IS NOT NULL AND value_numeric IS NULL) OR "
            "(value_text IS NULL AND value_numeric IS NOT NULL)",
            name="ck_lab_result_exactly_one_value",
        ),
        CheckConstraint(
            "abnormality IN ('not_flagged', 'low', 'high', 'critical', 'not_applicable')",
            name="ck_lab_result_abnormality",
        ),
        CheckConstraint("status IN ('preliminary', 'final')", name="ck_lab_result_status"),
        CheckConstraint(
            "(status = 'preliminary' AND verified_by_user_id IS NULL AND verified_at IS NULL) OR "
            "(status = 'final' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_lab_result_verification_state",
        ),
        CheckConstraint(
            "verified_by_user_id IS NULL OR verified_by_user_id != entered_by_user_id",
            name="ck_lab_result_two_person_verification",
        ),
        CheckConstraint(
            "critical_flag = false OR (critical_note IS NOT NULL AND length(trim(critical_note)) >= 3)",
            name="ck_lab_result_critical_note",
        ),
        CheckConstraint(
            "(abnormality = 'critical' AND critical_flag = true) OR "
            "(abnormality != 'critical' AND critical_flag = false)",
            name="ck_lab_result_critical_abnormality_flag",
        ),
        Index("ix_lab_result_status_time", "hospital_id", "status", "entered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    specimen_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    entered_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    unit: Mapped[str | None] = mapped_column(String(80))
    abnormality: Mapped[str] = mapped_column(String(24), nullable=False, default="not_flagged")
    interpretation_note: Mapped[str | None] = mapped_column(Text)
    critical_flag: Mapped[bool] = mapped_column(nullable=False, default=False)
    critical_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="preliminary")
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LaboratoryCriticalAcknowledgement(Base):
    __tablename__ = "laboratory_critical_acknowledgements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "result_id"],
            ["laboratory_results.hospital_id", "laboratory_results.id"],
            name="fk_lab_critical_ack_result",
        ),
        UniqueConstraint("hospital_id", "result_id", name="uq_lab_critical_ack_result"),
        CheckConstraint(
            "length(trim(acknowledgement_note)) >= 3",
            name="ck_lab_critical_ack_note",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    result_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    acknowledged_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    acknowledgement_note: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
