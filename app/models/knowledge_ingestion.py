import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, JSON, Numeric, String, Text,
    UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.core import TimestampMixin


class KnowledgeImportBatch(TimestampMixin, Base):
    """Tenant-scoped intake batch. Nothing in a batch is retrievable clinical knowledge."""

    __tablename__ = "knowledge_import_batches"
    __table_args__ = (
        CheckConstraint("scope IN ('global', 'hospital')", name="ck_knowledge_import_scope"),
        CheckConstraint(
            "(scope = 'global' AND hospital_id IS NULL) OR "
            "(scope = 'hospital' AND hospital_id IS NOT NULL)",
            name="ck_knowledge_import_scope_owner",
        ),
        CheckConstraint(
            "status IN ('received', 'validating', 'needs_review', 'rejected', 'closed')",
            name="ck_knowledge_import_status",
        ),
        Index("ix_knowledge_import_scope_hospital", "scope", "hospital_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospitals.id"), index=True)
    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("medical_knowledge_sources.id"))
    source_identity: Mapped[str] = mapped_column(String(240), nullable=False)
    declared_license: Mapped[str | None] = mapped_column(String(160))
    license_reference: Mapped[str | None] = mapped_column(String(500))
    license_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="received")
    validation_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class StagedKnowledgeDocument(TimestampMixin, Base):
    """Quarantined import payload; promotion requires a separate governed review."""

    __tablename__ = "staged_knowledge_documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('staged', 'duplicate', 'invalid', 'pending_review', 'rejected', 'promoted')",
            name="ck_staged_knowledge_status",
        ),
        UniqueConstraint("batch_id", "content_sha256", name="uq_staged_batch_content_hash"),
        Index("ix_staged_knowledge_hash", "content_sha256"),
        Index("ix_staged_knowledge_source_version", "source_identity", "external_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_import_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_identity: Mapped[str] = mapped_column(String(240), nullable=False)
    external_document_id: Mapped[str | None] = mapped_column(String(240))
    external_version: Mapped[str | None] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="en")
    jurisdiction: Mapped[str] = mapped_column(String(80), nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="staged")
    duplicate_of_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("medical_knowledge_documents.id")
    )
    validation_errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class TerminologyMapping(TimestampMixin, Base):
    """License-aware external code mapping; source terms are never bundled by this table."""

    __tablename__ = "terminology_mappings"
    __table_args__ = (
        CheckConstraint(
            "code_system IN ('ICD-10', 'SNOMED-CT', 'LOINC', 'LOCAL', 'OTHER')",
            name="ck_terminology_mapping_system",
        ),
        CheckConstraint(
            "status IN ('proposed', 'verified', 'rejected', 'retired')",
            name="ck_terminology_mapping_status",
        ),
        UniqueConstraint(
            "concept_id", "code_system", "code", "release_version",
            name="uq_terminology_mapping_release_code",
        ),
        Index("ix_terminology_mapping_lookup", "code_system", "code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinical_concepts.id", ondelete="CASCADE"), nullable=False)
    code_system: Mapped[str] = mapped_column(String(24), nullable=False)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    release_version: Mapped[str] = mapped_column(String(80), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(80), nullable=False)
    license_reference: Mapped[str | None] = mapped_column(String(500))
    license_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="proposed")
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LaboratoryUnitMapping(TimestampMixin, Base):
    """Explicitly reviewed unit aliases; this does not perform or infer conversions."""

    __tablename__ = "laboratory_unit_mappings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'verified', 'rejected', 'retired')",
            name="ck_lab_unit_mapping_status",
        ),
        UniqueConstraint(
            "source_unit", "canonical_unit", "specimen", "method",
            name="uq_lab_unit_mapping_context",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_unit: Mapped[str] = mapped_column(String(80), nullable=False)
    canonical_unit: Mapped[str] = mapped_column(String(80), nullable=False)
    specimen: Mapped[str | None] = mapped_column(String(100))
    method: Mapped[str | None] = mapped_column(String(160))
    conversion_factor: Mapped[Any | None] = mapped_column(Numeric(24, 12))
    conversion_offset: Mapped[Any | None] = mapped_column(Numeric(24, 12))
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="proposed")
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
