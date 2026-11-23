"""Add structured clinical knowledge taxonomy tables."""

from alembic import op
import sqlalchemy as sa

revision = "0004_clinical_taxonomy"
down_revision = "0003_medical_knowledge"
branch_labels = None
depends_on = None


def _tenant_rls(table: str, parent_column: str = "document_id") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY {table}_tenant_read ON {table}
        FOR SELECT USING (EXISTS (
            SELECT 1 FROM medical_knowledge_documents d
            JOIN medical_knowledge_sources s ON s.id = d.source_id
            WHERE d.id = {parent_column} AND (
                s.scope = 'global' OR s.hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            )
        ))
    """)
    op.execute(f"""
        CREATE POLICY {table}_hospital_write ON {table}
        FOR ALL USING (EXISTS (
            SELECT 1 FROM medical_knowledge_documents d
            JOIN medical_knowledge_sources s ON s.id = d.source_id
            WHERE d.id = {parent_column} AND s.scope = 'hospital' AND s.hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM medical_knowledge_documents d
            JOIN medical_knowledge_sources s ON s.id = d.source_id
            WHERE d.id = {parent_column} AND s.scope = 'hospital' AND s.hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        ))
    """)


def upgrade() -> None:
    op.create_table(
        "clinical_concepts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("concept_type", sa.String(32), nullable=False),
        sa.Column("preferred_term", sa.String(240), nullable=False),
        sa.Column("normalized_term", sa.String(240), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("code_system", sa.String(80), nullable=True),
        sa.Column("code", sa.String(120), nullable=True),
        sa.Column("language", sa.String(12), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("concept_type IN ('disease', 'symptom', 'finding', 'procedure', 'laboratory_test', 'imaging_test', 'medication', 'anatomy', 'organism', 'other')", name="ck_clinical_concept_type"),
        sa.ForeignKeyConstraint(["document_id"], ["medical_knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "concept_type", "code_system", "code", name="uq_clinical_concept_document_code"),
        sa.UniqueConstraint("document_id", "id", name="uq_clinical_concept_document_id"),
    )
    op.create_index("ix_clinical_concepts_document_id", "clinical_concepts", ["document_id"])
    op.create_index("ix_clinical_concept_type_term", "clinical_concepts", ["concept_type", "preferred_term"])
    op.create_index("ix_clinical_concepts_normalized_term", "clinical_concepts", ["normalized_term"])

    op.create_table(
        "clinical_concept_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("source_concept_id", sa.Uuid(), nullable=False),
        sa.Column("target_concept_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False),
        sa.Column("qualifier", sa.String(160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.CheckConstraint("relation_type IN ('has_symptom', 'has_finding', 'differential_for', 'investigated_by', 'treated_by', 'contraindicated_in', 'interacts_with', 'complication_of', 'associated_with', 'located_in', 'caused_by', 'other')", name="ck_clinical_concept_relation_type"),
        sa.CheckConstraint("source_concept_id <> target_concept_id", name="ck_clinical_concept_relation_not_self"),
        sa.ForeignKeyConstraint(["document_id"], ["medical_knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id", "source_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id", "target_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "source_concept_id", "relation_type", "target_concept_id", name="uq_clinical_concept_relation"),
    )
    op.create_index("ix_clinical_concept_relations_document_id", "clinical_concept_relations", ["document_id"])
    op.create_index("ix_clinical_relation_source_type", "clinical_concept_relations", ["source_concept_id", "relation_type"])
    op.create_index("ix_clinical_relation_target_type", "clinical_concept_relations", ["target_concept_id", "relation_type"])

    op.create_table(
        "laboratory_reference_intervals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("test_concept_id", sa.Uuid(), nullable=False),
        sa.Column("specimen", sa.String(100), nullable=True),
        sa.Column("unit", sa.String(80), nullable=False),
        sa.Column("lower_bound", sa.Numeric(18, 6), nullable=True),
        sa.Column("upper_bound", sa.Numeric(18, 6), nullable=True),
        sa.Column("age_min_days", sa.Integer(), nullable=True),
        sa.Column("age_max_days", sa.Integer(), nullable=True),
        sa.Column("sex_context", sa.String(40), nullable=True),
        sa.Column("pregnancy_context", sa.String(40), nullable=True),
        sa.Column("population_context", sa.String(160), nullable=True),
        sa.Column("method", sa.String(160), nullable=True),
        sa.Column("interpretation_notes", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound", name="ck_lab_interval_bounds"),
        sa.CheckConstraint("age_min_days IS NULL OR age_min_days >= 0", name="ck_lab_interval_age_min"),
        sa.CheckConstraint("age_max_days IS NULL OR age_min_days IS NULL OR age_max_days >= age_min_days", name="ck_lab_interval_age_order"),
        sa.ForeignKeyConstraint(["document_id"], ["medical_knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id", "test_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_laboratory_reference_intervals_document_id", "laboratory_reference_intervals", ["document_id"])
    op.create_index("ix_laboratory_reference_intervals_test_concept_id", "laboratory_reference_intervals", ["test_concept_id"])
    op.create_index("ix_lab_interval_test_context", "laboratory_reference_intervals", ["test_concept_id", "specimen", "unit"])

    op.create_table(
        "medication_safety_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("medication_concept_id", sa.Uuid(), nullable=False),
        sa.Column("related_concept_id", sa.Uuid(), nullable=True),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rule_type IN ('contraindication', 'interaction', 'caution', 'monitoring', 'pregnancy', 'lactation', 'renal', 'hepatic', 'dose_adjustment', 'other')", name="ck_medication_safety_rule_type"),
        sa.CheckConstraint("severity IN ('informational', 'low', 'moderate', 'high', 'critical')", name="ck_medication_safety_severity"),
        sa.ForeignKeyConstraint(["document_id"], ["medical_knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id", "medication_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id", "related_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_medication_safety_rules_document_id", "medication_safety_rules", ["document_id"])
    op.create_index("ix_medication_safety_rules_medication_concept_id", "medication_safety_rules", ["medication_concept_id"])
    op.create_index("ix_medication_safety_medication_type", "medication_safety_rules", ["medication_concept_id", "rule_type"])

    op.create_table(
        "emergency_escalation_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_concept_id", sa.Uuid(), nullable=False),
        sa.Column("urgency", sa.String(20), nullable=False),
        sa.Column("escalation_action", sa.Text(), nullable=False),
        sa.Column("target_service", sa.String(120), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.CheckConstraint("urgency IN ('urgent', 'emergency', 'immediate')", name="ck_emergency_escalation_urgency"),
        sa.ForeignKeyConstraint(["document_id"], ["medical_knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id", "trigger_concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emergency_escalation_rules_document_id", "emergency_escalation_rules", ["document_id"])
    op.create_index("ix_emergency_escalation_rules_trigger_concept_id", "emergency_escalation_rules", ["trigger_concept_id"])
    op.create_index("ix_emergency_escalation_trigger", "emergency_escalation_rules", ["trigger_concept_id", "urgency"])

    for table in (
        "clinical_concepts",
        "clinical_concept_relations",
        "laboratory_reference_intervals",
        "medication_safety_rules",
        "emergency_escalation_rules",
    ):
        _tenant_rls(table)


def downgrade() -> None:
    tables = (
        "emergency_escalation_rules",
        "medication_safety_rules",
        "laboratory_reference_intervals",
        "clinical_concept_relations",
        "clinical_concepts",
    )
    for table in tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_read ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_hospital_write ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_emergency_escalation_trigger", table_name="emergency_escalation_rules")
    op.drop_index("ix_emergency_escalation_rules_trigger_concept_id", table_name="emergency_escalation_rules")
    op.drop_index("ix_emergency_escalation_rules_document_id", table_name="emergency_escalation_rules")
    op.drop_table("emergency_escalation_rules")

    op.drop_index("ix_medication_safety_medication_type", table_name="medication_safety_rules")
    op.drop_index("ix_medication_safety_rules_medication_concept_id", table_name="medication_safety_rules")
    op.drop_index("ix_medication_safety_rules_document_id", table_name="medication_safety_rules")
    op.drop_table("medication_safety_rules")

    op.drop_index("ix_lab_interval_test_context", table_name="laboratory_reference_intervals")
    op.drop_index("ix_laboratory_reference_intervals_test_concept_id", table_name="laboratory_reference_intervals")
    op.drop_index("ix_laboratory_reference_intervals_document_id", table_name="laboratory_reference_intervals")
    op.drop_table("laboratory_reference_intervals")

    op.drop_index("ix_clinical_relation_target_type", table_name="clinical_concept_relations")
    op.drop_index("ix_clinical_relation_source_type", table_name="clinical_concept_relations")
    op.drop_index("ix_clinical_concept_relations_document_id", table_name="clinical_concept_relations")
    op.drop_table("clinical_concept_relations")

    op.drop_index("ix_clinical_concepts_normalized_term", table_name="clinical_concepts")
    op.drop_index("ix_clinical_concept_type_term", table_name="clinical_concepts")
    op.drop_index("ix_clinical_concepts_document_id", table_name="clinical_concepts")
    op.drop_table("clinical_concepts")
