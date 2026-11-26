import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON,
    String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DiagnosticSupportCase(Base):
    __tablename__ = "diagnostic_support_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "hospital_id", "owner_user_id"],
            ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"],
            name="fk_diagnostic_case_session_owner",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_diagnostic_case_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_diagnostic_case_encounter",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "consent_id", "patient_id"],
            ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"],
            name="fk_diagnostic_case_consent",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "closed_by_user_id"],
            ["hospital_memberships.hospital_id", "hospital_memberships.user_id"],
            name="fk_diagnostic_case_closer",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_diagnostic_case_hospital_id"),
        UniqueConstraint("hospital_id", "session_id", "source_assistant_sequence", name="uq_diagnostic_case_source_response"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_diagnostic_case_status"),
        CheckConstraint("source_assistant_sequence > 0", name="ck_diagnostic_case_source_sequence"),
        CheckConstraint("source_response_digest ~ '^[0-9a-f]{64}$'", name="ck_diagnostic_case_source_digest"),
        CheckConstraint("closure_reference IS NULL OR closure_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_diagnostic_case_closure_reference"),
        CheckConstraint("(status = 'open' AND closed_by_user_id IS NULL AND closed_at IS NULL AND closure_reference IS NULL) OR (status = 'closed' AND closed_by_user_id IS NOT NULL AND closed_at IS NOT NULL AND closure_reference IS NOT NULL)", name="ck_diagnostic_case_closure_state"),
        Index("ix_diagnostic_case_patient_status", "hospital_id", "patient_id", "status", "created_at"),
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
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    closure_reference: Mapped[str | None] = mapped_column(String(80))
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DiagnosticDifferentialSuggestion(Base):
    __tablename__ = "diagnostic_differential_suggestions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "case_id"],
            ["diagnostic_support_cases.hospital_id", "diagnostic_support_cases.id"],
            name="fk_diagnostic_differential_case",
        ),
        ForeignKeyConstraint(
            ["document_id", "concept_id"],
            ["clinical_concepts.document_id", "clinical_concepts.id"],
            name="fk_diagnostic_differential_concept",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "reviewed_by_user_id"],
            ["hospital_memberships.hospital_id", "hospital_memberships.user_id"],
            name="fk_diagnostic_differential_reviewer",
        ),
        UniqueConstraint("hospital_id", "case_id", "document_id", "concept_id", name="uq_diagnostic_differential_concept"),
        CheckConstraint("status IN ('proposed', 'considered', 'ruled_out', 'clinician_confirmed')", name="ck_diagnostic_differential_status"),
        CheckConstraint("json_typeof(evidence_citation_ids) = 'array' AND json_array_length(evidence_citation_ids) > 0", name="ck_diagnostic_differential_citations"),
        CheckConstraint("review_reference IS NULL OR review_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_diagnostic_differential_review_reference"),
        CheckConstraint("(status = 'proposed' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) OR (status != 'proposed' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_diagnostic_differential_review_state"),
        Index("ix_diagnostic_differential_case_status", "hospital_id", "case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    concept_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    concept_code: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    evidence_citation_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="proposed")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reference: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DiagnosticTestConsideration(Base):
    __tablename__ = "diagnostic_test_considerations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "case_id"],
            ["diagnostic_support_cases.hospital_id", "diagnostic_support_cases.id"],
            name="fk_diagnostic_test_case",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "laboratory_test_definition_id"],
            ["laboratory_test_definitions.hospital_id", "laboratory_test_definitions.id"],
            name="fk_diagnostic_test_laboratory_definition",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "imaging_procedure_definition_id"],
            ["imaging_procedure_definitions.hospital_id", "imaging_procedure_definitions.id"],
            name="fk_diagnostic_test_imaging_definition",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "reviewed_by_user_id"],
            ["hospital_memberships.hospital_id", "hospital_memberships.user_id"],
            name="fk_diagnostic_test_reviewer",
        ),
        UniqueConstraint("hospital_id", "case_id", "test_domain", "test_code", name="uq_diagnostic_test_consideration"),
        CheckConstraint("test_domain IN ('laboratory', 'imaging')", name="ck_diagnostic_test_domain"),
        CheckConstraint("(test_domain = 'laboratory' AND laboratory_test_definition_id IS NOT NULL AND imaging_procedure_definition_id IS NULL) OR (test_domain = 'imaging' AND imaging_procedure_definition_id IS NOT NULL AND laboratory_test_definition_id IS NULL)", name="ck_diagnostic_test_definition_pair"),
        CheckConstraint("status IN ('proposed', 'considered', 'declined')", name="ck_diagnostic_test_status"),
        CheckConstraint("json_typeof(evidence_citation_ids) = 'array' AND json_array_length(evidence_citation_ids) > 0", name="ck_diagnostic_test_citations"),
        CheckConstraint("review_reference IS NULL OR review_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_diagnostic_test_review_reference"),
        CheckConstraint("(status = 'proposed' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) OR (status != 'proposed' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_diagnostic_test_review_state"),
        Index("ix_diagnostic_test_case_status", "hospital_id", "case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    test_domain: Mapped[str] = mapped_column(String(16), nullable=False)
    laboratory_test_definition_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    imaging_procedure_definition_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    test_code: Mapped[str] = mapped_column(String(80), nullable=False)
    test_name: Mapped[str] = mapped_column(String(180), nullable=False)
    evidence_citation_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_reference: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
