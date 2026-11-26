import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClinicalAISessionContext(Base):
    __tablename__ = "clinical_ai_session_contexts"
    __table_args__ = (
        ForeignKeyConstraint(["session_id", "hospital_id", "owner_user_id"], ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"], name="fk_clinical_ai_context_session_owner"),
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_clinical_ai_context_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_clinical_ai_context_encounter"),
        ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_clinical_ai_context_consent"),
        
        UniqueConstraint("hospital_id", "session_id", name="uq_clinical_ai_context_session"),
        CheckConstraint("status IN ('active', 'revoked', 'expired')", name="ck_clinical_ai_context_status"),
        Index("ix_clinical_ai_context_patient", "hospital_id", "patient_id", "encounter_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    consent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_care_assignments.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIClinicalReviewRecord(Base):
    __tablename__ = "ai_clinical_review_records"
    __table_args__ = (
        ForeignKeyConstraint(["session_id", "hospital_id", "owner_user_id"], ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"], name="fk_ai_clinical_review_session_owner"),
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_ai_clinical_review_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_ai_clinical_review_encounter"),
        ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_ai_clinical_review_reviewer"),
        UniqueConstraint("hospital_id", "session_id", "assistant_sequence", name="uq_ai_clinical_review_sequence"),
        CheckConstraint("decision IN ('accepted_for_consideration', 'rejected', 'needs_revision')", name="ck_ai_clinical_review_decision"),
        CheckConstraint("assistant_sequence > 0", name="ck_ai_clinical_review_sequence"),
        CheckConstraint("response_digest ~ '^[0-9a-f]{64}$'", name="ck_ai_clinical_review_digest"),
        CheckConstraint("note_reference IS NULL OR note_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_ai_clinical_review_note_ref"),
        Index("ix_ai_clinical_review_patient", "hospital_id", "patient_id", "reviewed_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    assistant_sequence: Mapped[int] = mapped_column(nullable=False)
    response_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    note_reference: Mapped[str | None] = mapped_column(String(80))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_ai_clinical_review_digest"),
        CheckConstraint("note_reference IS NULL OR note_reference ~ '^vault://[0-9a-fA-F-]{36}
        Index("ix_ai_clinical_review_patient", "hospital_id", "patient_id", "reviewed_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    assistant_sequence: Mapped[int] = mapped_column(nullable=False)
    response_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    note_reference: Mapped[str | None] = mapped_column(String(80))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_ai_clinical_review_note_ref"),
        Index("ix_ai_clinical_review_patient", "hospital_id", "patient_id", "reviewed_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    assistant_sequence: Mapped[int] = mapped_column(nullable=False)
    response_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    note_reference: Mapped[str | None] = mapped_column(String(80))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
