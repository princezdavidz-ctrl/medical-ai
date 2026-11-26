import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    JSON, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DiagnosticSupportCase(Base):
    __tablename__ = "diagnostic_support_cases"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_diagnostic_case_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_diagnostic_case_encounter"),
        ForeignKeyConstraint(["hospital_id", "session_id"], ["clinical_ai_session_contexts.hospital_id", "clinical_ai_session_contexts.session_id"], name="fk_diagnostic_case_ai_session"),
        ForeignKeyConstraint(["hospital_id", "created_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_case_creator"),
        UniqueConstraint("hospital_id", "id", name="uq_diagnostic_case_hospital_id"),
        CheckConstraint("status IN ('open', 'under_review', 'closed')", name="ck_diagnostic_case_status"),
        CheckConstraint("length(trim(problem_representation)) BETWEEN 10 AND 4000", name="ck_diagnostic_case_problem"),
        CheckConstraint("status != 'closed' OR (clinician_assessment IS NOT NULL AND closed_by_user_id IS NOT NULL AND closed_at IS NOT NULL)", name="ck_diagnostic_case_closure"),
        Index("ix_diagnostic_case_patient", "hospital_id", "patient_id", "created_at"),
        Index("ix_diagnostic_case_encounter", "hospital_id", "encounter_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    problem_representation: Mapped[str] = mapped_column(Text, nullable=False)
    known_findings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    missing_information: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    red_flags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    clinician_assessment: Mapped[str | None] = mapped_column(Text)
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DiagnosticDifferential(Base):
    __tablename__ = "diagnostic_differentials"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "case_id"], ["diagnostic_support_cases.hospital_id", "diagnostic_support_cases.id"], name="fk_diagnostic_differential_case"),
        ForeignKeyConstraint(["hospital_id", "entered_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_differential_author"),
        ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_differential_reviewer"),
        UniqueConstraint("hospital_id", "case_id", "concept_code", name="uq_diagnostic_differential_concept"),
        CheckConstraint("status IN ('proposed', 'considered', 'ruled_out', 'clinician_confirmed')", name="ck_diagnostic_differential_status"),
        CheckConstraint("source_digest ~ '^[0-9a-f]{64}$'", name="ck_diagnostic_differential_digest"),
        CheckConstraint("length(trim(display_name)) BETWEEN 2 AND 180", name="ck_diagnostic_differential_name"),
        Index("ix_diagnostic_differential_case", "hospital_id", "case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    concept_code: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source_sequence: Mapped[int] = mapped_column(nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_citation_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="proposed")
    entered_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DiagnosticTestConsideration(Base):
    __tablename__ = "diagnostic_test_considerations"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "case_id"], ["diagnostic_support_cases.hospital_id", "diagnostic_support_cases.id"], name="fk_diagnostic_test_case"),
        ForeignKeyConstraint(["hospital_id", "entered_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_test_author"),
        ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_test_reviewer"),
        UniqueConstraint("hospital_id", "case_id", "test_code", "modality", name="uq_diagnostic_test_consideration"),
        CheckConstraint("modality IN ('laboratory', 'imaging', 'procedure', 'other')", name="ck_diagnostic_test_modality"),
        CheckConstraint("priority IN ('routine', 'urgent', 'stat_consideration')", name="ck_diagnostic_test_priority"),
        CheckConstraint("status IN ('proposed', 'considered', 'declined')", name="ck_diagnostic_test_status"),
        CheckConstraint("source_digest ~ '^[0-9a-f]{64}$'", name="ck_diagnostic_test_digest"),
        CheckConstraint("length(trim(test_name)) BETWEEN 2 AND 180", name="ck_diagnostic_test_name"),
        Index("ix_diagnostic_test_case", "hospital_id", "case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    test_code: Mapped[str] = mapped_column(String(80), nullable=False)
    test_name: Mapped[str] = mapped_column(String(180), nullable=False)
    modality: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(String(24), nullable=False, default="routine")
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source_sequence: Mapped[int] = mapped_column(nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_citation_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")
    entered_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
