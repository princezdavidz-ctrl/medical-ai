import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON,
    Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClinicalConcept(Base):
    """A coded clinical term grounded in one governed knowledge document."""

    __tablename__ = "clinical_concepts"
    __table_args__ = (
        CheckConstraint(
            "concept_type IN ('disease', 'symptom', 'finding', 'procedure', "
            "'laboratory_test', 'imaging_test', 'medication', 'anatomy', 'organism', 'other')",
            name="ck_clinical_concept_type",
        ),
        UniqueConstraint("document_id", "concept_type", "code_system", "code", name="uq_clinical_concept_document_code"),
        UniqueConstraint("document_id", "id", name="uq_clinical_concept_document_id"),
        Index("ix_clinical_concept_type_term", "concept_type", "preferred_term"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_type: Mapped[str] = mapped_column(String(32), nullable=False)
    preferred_term: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_term: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    definition: Mapped[str | None] = mapped_column(Text)
    code_system: Mapped[str | None] = mapped_column(String(80))
    code: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="en")
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClinicalConceptRelation(Base):
    """Typed, source-attributed links between concepts in the same governed document."""

    __tablename__ = "clinical_concept_relations"
    __table_args__ = (
        CheckConstraint(
            "relation_type IN ('has_symptom', 'has_finding', 'differential_for', "
            "'investigated_by', 'treated_by', 'contraindicated_in', 'interacts_with', "
            "'complication_of', 'associated_with', 'located_in', 'caused_by', 'other')",
            name="ck_clinical_concept_relation_type",
        ),
        CheckConstraint("source_concept_id <> target_concept_id", name="ck_clinical_concept_relation_not_self"),
        UniqueConstraint("document_id", "source_concept_id", "relation_type", "target_concept_id", name="uq_clinical_concept_relation"),
        ForeignKeyConstraint(["document_id", "source_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["document_id", "target_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        Index("ix_clinical_relation_source_type", "source_concept_id", "relation_type"),
        Index("ix_clinical_relation_target_type", "target_concept_id", "relation_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    source_concept_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    target_concept_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    qualifier: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class LaboratoryReferenceInterval(Base):
    """Context-specific reference interval, not a universal normal/abnormal rule."""

    __tablename__ = "laboratory_reference_intervals"
    __table_args__ = (
        CheckConstraint("lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound", name="ck_lab_interval_bounds"),
        CheckConstraint("age_min_days IS NULL OR age_min_days >= 0", name="ck_lab_interval_age_min"),
        CheckConstraint("age_max_days IS NULL OR age_min_days IS NULL OR age_max_days >= age_min_days", name="ck_lab_interval_age_order"),
        ForeignKeyConstraint(["document_id", "test_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        Index("ix_lab_interval_test_context", "test_concept_id", "specimen", "unit"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    test_concept_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    specimen: Mapped[str | None] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(80), nullable=False)
    lower_bound: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    age_min_days: Mapped[int | None] = mapped_column()
    age_max_days: Mapped[int | None] = mapped_column()
    sex_context: Mapped[str | None] = mapped_column(String(40))
    pregnancy_context: Mapped[str | None] = mapped_column(String(40))
    population_context: Mapped[str | None] = mapped_column(String(160))
    method: Mapped[str | None] = mapped_column(String(160))
    interpretation_notes: Mapped[str | None] = mapped_column(Text)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MedicationSafetyRule(Base):
    """Reviewed medication safety rule with explicit scope and source provenance."""

    __tablename__ = "medication_safety_rules"
    __table_args__ = (
        CheckConstraint(
            "rule_type IN ('contraindication', 'interaction', 'caution', 'monitoring', "
            "'pregnancy', 'lactation', 'renal', 'hepatic', 'dose_adjustment', 'other')",
            name="ck_medication_safety_rule_type",
        ),
        CheckConstraint("severity IN ('informational', 'low', 'moderate', 'high', 'critical')", name="ck_medication_safety_severity"),
        ForeignKeyConstraint(["document_id", "medication_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["document_id", "related_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        Index("ix_medication_safety_medication_type", "medication_concept_id", "rule_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    medication_concept_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    related_concept_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmergencyEscalationRule(Base):
    """Source-backed red-flag/escalation definition; not an autonomous triage decision."""

    __tablename__ = "emergency_escalation_rules"
    __table_args__ = (
        CheckConstraint("urgency IN ('urgent', 'emergency', 'immediate')", name="ck_emergency_escalation_urgency"),
        ForeignKeyConstraint(["document_id", "trigger_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        Index("ix_emergency_escalation_trigger", "trigger_concept_id", "urgency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger_concept_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False)
    escalation_action: Mapped[str] = mapped_column(Text, nullable=False)
    target_service: Mapped[str | None] = mapped_column(String(120))
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
