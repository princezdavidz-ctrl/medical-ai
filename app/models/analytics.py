import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportDefinition(Base):
    __tablename__ = "report_definitions"
    __table_args__ = (
        UniqueConstraint("hospital_id", "report_code", "version", name="uq_report_definition_version"),
        UniqueConstraint("hospital_id", "id", name="uq_report_definition_hospital_id"),
        CheckConstraint("report_key IN ('patient_flow', 'bed_occupancy', 'emergency_volume', 'billing_summary', 'quality_safety', 'compliance_overview')", name="ck_report_definition_key"),
        CheckConstraint("data_domain IN ('clinical', 'operations', 'finance', 'quality', 'compliance')", name="ck_report_definition_domain"),
        CheckConstraint("status IN ('draft', 'published', 'retired')", name="ck_report_definition_status"),
        CheckConstraint("version >= 1", name="ck_report_definition_version"),
        CheckConstraint("json_typeof(required_roles) = 'array'", name="ck_report_definition_roles"),
        CheckConstraint("(status = 'published' AND published_by_user_id IS NOT NULL AND published_at IS NOT NULL) OR (status != 'published' AND published_by_user_id IS NULL AND published_at IS NULL)", name="ck_report_definition_publish_state"),
        Index("ix_report_definition_catalog", "hospital_id", "data_domain", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    report_code: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    report_key: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    data_domain: Mapped[str] = mapped_column(String(24), nullable=False)
    required_roles: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    department_scoped: Mapped[bool] = mapped_column(nullable=False, default=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReportRun(Base):
    __tablename__ = "report_runs"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "definition_id"], ["report_definitions.hospital_id", "report_definitions.id"], name="fk_report_run_definition"),
        CheckConstraint("status IN ('completed', 'failed', 'expired')", name="ck_report_run_status"),
        CheckConstraint("expires_at > generated_at", name="ck_report_run_expiry"),
        Index("ix_report_run_history", "hospital_id", "requested_by_user_id", "generated_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    definition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_versions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReportExportJob(Base):
    __tablename__ = "report_export_jobs"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "run_id"], ["report_runs.hospital_id", "report_runs.id"], name="fk_report_export_run"),
        CheckConstraint("format IN ('csv', 'pdf')", name="ck_report_export_format"),
        CheckConstraint("status IN ('queued', 'processing', 'completed', 'failed', 'expired')", name="ck_report_export_status"),
        CheckConstraint("output_reference IS NULL OR output_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_report_export_reference"),
        Index("ix_report_export_queue", "hospital_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    output_reference: Mapped[str | None] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
