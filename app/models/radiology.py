import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImagingProcedureDefinition(Base):
    __tablename__ = "imaging_procedure_definitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_imaging_definition_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_imaging_definition_hospital_id"),
        UniqueConstraint("hospital_id", "code", name="uq_imaging_definition_code"),
        CheckConstraint(
            "modality IN ('xray', 'ct', 'mri', 'ultrasound', 'mammography', 'fluoroscopy', 'nuclear_medicine', 'pet', 'other')",
            name="ck_imaging_definition_modality",
        ),
        CheckConstraint(
            "contrast_policy IN ('none', 'optional', 'required', 'not_applicable')",
            name="ck_imaging_definition_contrast",
        ),
        CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_imaging_definition_status"),
        CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'active' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NOT NULL AND retired_at IS NOT NULL "
            "AND retirement_reason IS NOT NULL AND length(trim(retirement_reason)) >= 3)",
            name="ck_imaging_definition_approval_state",
        ),
        CheckConstraint(
            "approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id",
            name="ck_imaging_definition_two_person",
        ),
        CheckConstraint(
            "length(trim(code)) >= 2 AND length(trim(name)) >= 2 "
            "AND length(trim(body_region)) >= 2",
            name="ck_imaging_definition_text",
        ),
        Index("ix_imaging_definition_department_status", "hospital_id", "department_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    modality: Mapped[str] = mapped_column(String(24), nullable=False)
    body_region: Mapped[str] = mapped_column(String(120), nullable=False)
    contrast_policy: Mapped[str] = mapped_column(String(24), nullable=False, default="not_applicable")
    preparation_instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirement_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ImagingOrder(Base):
    __tablename__ = "imaging_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_imaging_order_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_imaging_order_encounter_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "ordering_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_imaging_order_ordering_department",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "imaging_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_imaging_order_imaging_department",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "procedure_definition_id"],
            ["imaging_procedure_definitions.hospital_id", "imaging_procedure_definitions.id"],
            name="fk_imaging_order_definition",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_imaging_order_hospital_id"),
        CheckConstraint("status IN ('ordered', 'scheduled', 'in_progress', 'completed', 'cancelled')", name="ck_imaging_order_status"),
        CheckConstraint("priority IN ('routine', 'urgent', 'stat')", name="ck_imaging_order_priority"),
        CheckConstraint("length(trim(clinical_indication)) >= 3", name="ck_imaging_order_indication"),
        CheckConstraint(
            "(status = 'cancelled' AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL "
            "AND length(trim(cancellation_reason)) >= 3) OR "
            "(status != 'cancelled' AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL AND cancellation_reason IS NULL)",
            name="ck_imaging_order_cancellation_state",
        ),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status != 'completed' AND completed_at IS NULL)",
            name="ck_imaging_order_completion_state",
        ),
        Index("ix_imaging_order_patient_encounter", "hospital_id", "patient_id", "encounter_id"),
        Index("ix_imaging_order_queue", "hospital_id", "imaging_department_id", "status", "ordered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ordering_department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    imaging_department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    procedure_definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ordered_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="routine")
    clinical_indication: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ordered")
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)


class ImagingStudy(Base):
    __tablename__ = "imaging_studies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "order_id"],
            ["imaging_orders.hospital_id", "imaging_orders.id"],
            name="fk_imaging_study_order",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_imaging_study_hospital_id"),
        UniqueConstraint("hospital_id", "order_id", name="uq_imaging_study_order"),
        UniqueConstraint("hospital_id", "accession_number", name="uq_imaging_study_accession"),
        CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'completed', 'cancelled')",
            name="ck_imaging_study_status",
        ),
        CheckConstraint(
            "(status = 'scheduled' AND scheduled_at IS NOT NULL AND started_at IS NULL "
            "AND completed_at IS NULL AND cancelled_at IS NULL) OR "
            "(status = 'in_progress' AND scheduled_at IS NOT NULL AND started_at IS NOT NULL "
            "AND completed_at IS NULL AND cancelled_at IS NULL) OR "
            "(status = 'completed' AND scheduled_at IS NOT NULL AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL AND cancelled_at IS NULL) OR "
            "(status = 'cancelled' AND scheduled_at IS NOT NULL AND cancelled_at IS NOT NULL)",
            name="ck_imaging_study_workflow_timestamps",
        ),
        CheckConstraint(
            "length(trim(accession_number)) >= 2",
            name="ck_imaging_study_accession_text",
        ),
        Index("ix_imaging_study_queue", "hospital_id", "status", "scheduled_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(100), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    performed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="scheduled")
    pacs_system_reference: Mapped[str | None] = mapped_column(String(160))
    pacs_study_uid: Mapped[str | None] = mapped_column(String(100))


class ImagingReport(Base):
    __tablename__ = "imaging_reports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "study_id"],
            ["imaging_studies.hospital_id", "imaging_studies.id"],
            name="fk_imaging_report_study",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_imaging_report_hospital_id"),
        UniqueConstraint("hospital_id", "study_id", name="uq_imaging_report_study"),
        CheckConstraint("status IN ('preliminary', 'final')", name="ck_imaging_report_status"),
        CheckConstraint(
            "(status = 'preliminary' AND verified_by_user_id IS NULL AND verified_at IS NULL) OR "
            "(status = 'final' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_imaging_report_verification_state",
        ),
        CheckConstraint(
            "verified_by_user_id IS NULL OR verified_by_user_id != entered_by_user_id",
            name="ck_imaging_report_two_person",
        ),
        CheckConstraint(
            "length(trim(findings)) >= 3 AND length(trim(impression)) >= 3",
            name="ck_imaging_report_content",
        ),
        CheckConstraint(
            "critical_flag = false OR (critical_note IS NOT NULL AND length(trim(critical_note)) >= 3)",
            name="ck_imaging_report_critical_note",
        ),
        Index("ix_imaging_report_status_time", "hospital_id", "status", "entered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    study_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    entered_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    findings: Mapped[str] = mapped_column(Text, nullable=False)
    impression: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="preliminary")
    critical_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    critical_note: Mapped[str | None] = mapped_column(Text)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ImagingCriticalAcknowledgement(Base):
    __tablename__ = "imaging_critical_acknowledgements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "report_id"],
            ["imaging_reports.hospital_id", "imaging_reports.id"],
            name="fk_imaging_critical_ack_report",
        ),
        UniqueConstraint("hospital_id", "report_id", name="uq_imaging_critical_ack_report"),
        CheckConstraint("length(trim(acknowledgement_note)) >= 3", name="ck_imaging_critical_ack_note"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    acknowledged_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    acknowledgement_note: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
