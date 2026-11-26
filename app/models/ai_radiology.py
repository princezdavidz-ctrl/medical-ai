import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    JSON, String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIRadiologyInterpretationCase(Base):
    __tablename__ = "ai_radiology_interpretation_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "hospital_id", "owner_user_id"],
            ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"],
            name="fk_ai_radiology_case_session_owner",
        ),
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_ai_radiology_case_patient"),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_ai_radiology_case_encounter",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "consent_id", "patient_id"],
            ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"],
            name="fk_ai_radiology_case_consent",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "report_id"],
            ["imaging_reports.hospital_id", "imaging_reports.id"],
            name="fk_ai_radiology_case_report",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "reviewed_by_user_id"],
            ["hospital_memberships.hospital_id", "hospital_memberships.user_id"],
            name="fk_ai_radiology_case_reviewer",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_ai_radiology_case_hospital_id"),
        UniqueConstraint("hospital_id", "session_id", "source_assistant_sequence", name="uq_ai_radiology_case_source"),
        CheckConstraint("source_assistant_sequence > 0", name="ck_ai_radiology_case_sequence"),
        CheckConstraint("source_response_digest ~ '^[0-9a-f]{64}$'", name="ck_ai_radiology_case_response_digest"),
        CheckConstraint("report_digest ~ '^[0-9a-f]{64}$'", name="ck_ai_radiology_case_report_digest"),
        CheckConstraint("json_typeof(report_snapshot) = 'object'", name="ck_ai_radiology_case_snapshot"),
        CheckConstraint("status IN ('pending_review', 'reviewed', 'stale')", name="ck_ai_radiology_case_status"),
        CheckConstraint("review_reference IS NULL OR review_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_ai_radiology_case_review_reference"),
        CheckConstraint("review_note_reference IS NULL OR review_note_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_ai_radiology_case_note_reference"),
        CheckConstraint(
            "(status = 'pending_review' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND review_decision IS NULL) OR "
            "(status IN ('reviewed', 'stale') AND ((reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND review_decision IS NULL) OR "
            "(reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND review_decision IS NOT NULL)))",
            name="ck_ai_radiology_case_review_state",
        ),
        Index("ix_ai_radiology_case_patient_created", "hospital_id", "patient_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    consent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_care_assignments.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    study_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    report_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    report_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_assistant_sequence: Mapped[int] = mapped_column(nullable=False)
    source_response_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_review")
    review_decision: Mapped[str | None] = mapped_column(String(32))
    review_reference: Mapped[str | None] = mapped_column(String(80))
    review_note_reference: Mapped[str | None] = mapped_column(String(80))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
