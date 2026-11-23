import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.core import TimestampMixin


class ClinicalKnowledgeReviewerAuthorization(TimestampMixin, Base):
    """Platform-verified professional authorization for governed knowledge review."""

    __tablename__ = "clinical_knowledge_reviewer_authorizations"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'active', 'suspended', 'revoked')", name="ck_knowledge_reviewer_auth_status"),
        Index("ix_knowledge_reviewer_auth_user_scope", "user_id", "scope", "hospital_id"),
        CheckConstraint("(scope = 'global' AND hospital_id IS NULL) OR (scope = 'hospital' AND hospital_id IS NOT NULL)", name="ck_knowledge_reviewer_auth_scope"),
        CheckConstraint("verified_by_user_id <> user_id", name="ck_knowledge_reviewer_verified_by_other"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospitals.id"))
    professional_registration: Mapped[str] = mapped_column(String(160), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(100), nullable=False)
    credential_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    verified_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")


class KnowledgeReviewEvent(Base):
    """Append-only decision history; updates/deletes are denied by database policy."""

    __tablename__ = "knowledge_review_events"
    __table_args__ = (
        CheckConstraint("decision IN ('submitted', 'approved', 'rejected', 'published', 'superseded')", name="ck_knowledge_review_event_decision"),
        Index("ix_knowledge_review_event_document_time", "staged_document_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staged_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staged_knowledge_documents.id"), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewer_authorization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clinical_knowledge_reviewer_authorizations.id"))
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
