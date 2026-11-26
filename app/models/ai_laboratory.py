import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON,
    String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AILaboratoryInterpretationCase(Base):
    __tablename__ = "ai_laboratory_interpretation_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "hospital_id", "owner_user_id"],
            ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"],
            name="fk_ai_lab_case_session_owner",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_ai_lab_case_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_ai_lab_case_encounter",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "consent_id", "patient_id"],
            ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"],
            name="fk_ai_lab_case_consent",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "reviewed_by_user_id"],
            ["hospital_memberships.hospital_id", "hospital_memberships.user_id"],
            name="fk_ai_lab_case_reviewer",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_ai_lab_case_hospital_id"),
        UniqueConstraint("hospital_id", "session_id", "source_assistant_sequence", name="uq_ai_lab_case_source"),
        CheckConstraint("source_assistant_sequence > 0", name="ck_ai_lab_case_sequence"),
        CheckConstraint("source_response_digest ~ '^[0-9a-f]{64}$'", name="ck_ai_lab_case_digest"),
        CheckConstraint(
            "json_typeof(laboratory_result_ids) = 'array' AND json_array_length(laboratory_result_ids) > 0",
            name="ck_ai_lab_case_result_ids",
        ),
        CheckConstraint(
            "json_typeof(result_snapshot) = 'array' AND json_array_length(result_snapshot) > 0",
            name="ck_ai_lab_case_snapshot",
        ),
        CheckConstraint("json_typeof(evidence_citation_ids) = 'array'", name="ck_ai_lab_case_citations"),
        CheckConstraint("status IN ('pending_review', 'reviewed')", name="ck_ai_lab_case_status"),
        CheckConstraint(
            "review_reference IS NULL OR review_reference ~ '^vault://[0-9a-fA-F-]{36}$'",
            name="ck_ai_lab_case_review_reference",
        ),
        CheckConstraint(
            "review_note_reference IS NULL OR review_note_reference ~ '^vault://[0-9a-fA-F-]{36}$'",
            name="ck_ai_lab_case_note_reference",
        ),
        CheckConstraint(
            "review_decision IS NULL OR review_decision IN "
            "('accepted_for_clinical_consideration', 'needs_correction', 'not_applicable')",
            name="ck_ai_lab_case_review_decision",
        ),
        CheckConstraint(
            "(status = 'pending_review' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND review_decision IS NULL) OR "
            "(status = 'reviewed' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND review_decision IS NOT NULL)",
            name="ck_ai_lab_case_review_state",
        ),
        Index("ix_ai_lab_case_patient_created", "hospital_id", "patient_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    consent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_care_assignments.id"), nullable=False)
    source_assistant_sequence: Mapped[int] = mapped_column(nullable=False)
    source_response_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    laboratory_result_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    result_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    evidence_citation_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_review")
    review_decision: Mapped[str | None] = mapped_column(String(40))
    review_note_reference: Mapped[str | None] = mapped_column(String(80))
    review_reference: Mapped[str | None] = mapped_column(String(80))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
