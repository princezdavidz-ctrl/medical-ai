import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.core import TimestampMixin


class MedicalKnowledgeSource(TimestampMixin, Base):
    """Governed publisher/source metadata; global sources are shared read-only."""

    __tablename__ = "medical_knowledge_sources"
    __table_args__ = (
        CheckConstraint("scope IN ('global', 'hospital')", name="ck_knowledge_source_scope"),
        CheckConstraint("(scope = 'global' AND hospital_id IS NULL) OR (scope = 'hospital' AND hospital_id IS NOT NULL)", name="ck_knowledge_source_scope_owner"),
        CheckConstraint("status IN ('active', 'retired')", name="ck_knowledge_source_status"),
        Index("ix_knowledge_source_scope_hospital", "scope", "hospital_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="global")
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospitals.id"), index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    publisher: Mapped[str] = mapped_column(String(240), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    license_name: Mapped[str | None] = mapped_column(String(160))
    license_reference: Mapped[str | None] = mapped_column(String(240))
    jurisdiction: Mapped[str] = mapped_column(String(80), nullable=False, default="international")
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="en")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")


class MedicalKnowledgeDocument(TimestampMixin, Base):
    """Versioned clinical content with an explicit review and approval lifecycle."""

    __tablename__ = "medical_knowledge_documents"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'pending_review', 'approved', 'rejected', 'superseded', 'archived')", name="ck_knowledge_document_status"),
        Index("ix_knowledge_document_source_status", "source_id", "status"),
        Index("ix_knowledge_document_review_dates", "status", "effective_from", "effective_to"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False, default="clinical_reference")
    clinical_domain: Mapped[str | None] = mapped_column(String(100))
    summary: Mapped[str | None] = mapped_column(Text)
    publication_date: Mapped[date | None] = mapped_column(Date)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_grade: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("medical_knowledge_documents.id"))


class MedicalKnowledgeChunk(Base):
    """Searchable text fragment; retrieval must always join its approved document."""

    __tablename__ = "medical_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "sequence", name="uq_knowledge_chunk_document_sequence"),
        Index("ix_knowledge_chunk_document", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_knowledge_documents.id", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
