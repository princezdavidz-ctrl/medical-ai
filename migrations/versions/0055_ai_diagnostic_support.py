"""Add patient-bound diagnostic support cases and clinician-reviewed suggestions."""
from alembic import op
import sqlalchemy as sa

revision = "0055_ai_diagnostic_support"
down_revision = "0054_ai_clinical_feedback"
branch_labels = None
depends_on = None

TABLES = (
    "diagnostic_support_cases",
    "diagnostic_differential_suggestions",
    "diagnostic_test_considerations",
)


def upgrade() -> None:
    op.create_table(
        "diagnostic_support_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("consent_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), sa.ForeignKey("patient_care_assignments.id"), nullable=False),
        sa.Column("source_assistant_sequence", sa.Integer(), nullable=False),
        sa.Column("source_response_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("closure_reference", sa.String(80)),
        sa.Column("closed_by_user_id", sa.Uuid()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id", "hospital_id", "owner_user_id"], ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"], name="fk_diagnostic_case_session_owner"),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_diagnostic_case_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_diagnostic_case_encounter"),
        sa.ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_diagnostic_case_consent"),
        sa.ForeignKeyConstraint(["hospital_id", "closed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_case_closer"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_diagnostic_case_hospital_id"),
        sa.UniqueConstraint("hospital_id", "session_id", "source_assistant_sequence", name="uq_diagnostic_case_source_response"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_diagnostic_case_status"),
        sa.CheckConstraint("source_assistant_sequence > 0", name="ck_diagnostic_case_source_sequence"),
        sa.CheckConstraint("source_response_digest ~ '^[0-9a-f]{64}$'", name="ck_diagnostic_case_source_digest"),
        sa.CheckConstraint("closure_reference IS NULL OR closure_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_diagnostic_case_closure_reference"),
        sa.CheckConstraint("(status = 'open' AND closed_by_user_id IS NULL AND closed_at IS NULL AND closure_reference IS NULL) OR (status = 'closed' AND closed_by_user_id IS NOT NULL AND closed_at IS NOT NULL AND closure_reference IS NOT NULL)", name="ck_diagnostic_case_closure_state"),
    )
    op.create_index("ix_diagnostic_case_patient_status", "diagnostic_support_cases", ["hospital_id", "patient_id", "status", "created_at"])

    op.create_table(
        "diagnostic_differential_suggestions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("concept_code", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(240), nullable=False),
        sa.Column("evidence_citation_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(24), nullable=False, server_default="proposed"),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_reference", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["hospital_id", "case_id"], ["diagnostic_support_cases.hospital_id", "diagnostic_support_cases.id"], name="fk_diagnostic_differential_case"),
        sa.ForeignKeyConstraint(["document_id", "concept_id"], ["clinical_concepts.document_id", "clinical_concepts.id"], name="fk_diagnostic_differential_concept"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_differential_reviewer"),
        sa.UniqueConstraint("hospital_id", "case_id", "document_id", "concept_id", name="uq_diagnostic_differential_concept"),
        sa.CheckConstraint("status IN ('proposed', 'considered', 'ruled_out', 'clinician_confirmed')", name="ck_diagnostic_differential_status"),
        sa.CheckConstraint("json_typeof(evidence_citation_ids) = 'array' AND json_array_length(evidence_citation_ids) > 0", name="ck_diagnostic_differential_citations"),
        sa.CheckConstraint("review_reference IS NULL OR review_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_diagnostic_differential_review_reference"),
        sa.CheckConstraint("(status = 'proposed' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) OR (status != 'proposed' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_diagnostic_differential_review_state"),
    )
    op.create_index("ix_diagnostic_differential_case_status", "diagnostic_differential_suggestions", ["hospital_id", "case_id", "status"])

    op.create_table(
        "diagnostic_test_considerations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("test_domain", sa.String(16), nullable=False),
        sa.Column("laboratory_test_definition_id", sa.Uuid()),
        sa.Column("imaging_procedure_definition_id", sa.Uuid()),
        sa.Column("test_code", sa.String(80), nullable=False),
        sa.Column("test_name", sa.String(180), nullable=False),
        sa.Column("evidence_citation_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_reference", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["hospital_id", "case_id"], ["diagnostic_support_cases.hospital_id", "diagnostic_support_cases.id"], name="fk_diagnostic_test_case"),
        sa.ForeignKeyConstraint(["hospital_id", "laboratory_test_definition_id"], ["laboratory_test_definitions.hospital_id", "laboratory_test_definitions.id"], name="fk_diagnostic_test_laboratory_definition"),
        sa.ForeignKeyConstraint(["hospital_id", "imaging_procedure_definition_id"], ["imaging_procedure_definitions.hospital_id", "imaging_procedure_definitions.id"], name="fk_diagnostic_test_imaging_definition"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_test_reviewer"),
        sa.UniqueConstraint("hospital_id", "case_id", "test_domain", "test_code", name="uq_diagnostic_test_consideration"),
        sa.CheckConstraint("test_domain IN ('laboratory', 'imaging')", name="ck_diagnostic_test_domain"),
        sa.CheckConstraint("(test_domain = 'laboratory' AND laboratory_test_definition_id IS NOT NULL AND imaging_procedure_definition_id IS NULL) OR (test_domain = 'imaging' AND imaging_procedure_definition_id IS NOT NULL AND laboratory_test_definition_id IS NULL)", name="ck_diagnostic_test_definition_pair"),
        sa.CheckConstraint("status IN ('proposed', 'considered', 'declined')", name="ck_diagnostic_test_status"),
        sa.CheckConstraint("json_typeof(evidence_citation_ids) = 'array' AND json_array_length(evidence_citation_ids) > 0", name="ck_diagnostic_test_citations"),
        sa.CheckConstraint("review_reference IS NULL OR review_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_diagnostic_test_review_reference"),
        sa.CheckConstraint("(status = 'proposed' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) OR (status != 'proposed' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_diagnostic_test_review_state"),
    )
    op.create_index("ix_diagnostic_test_case_status", "diagnostic_test_considerations", ["hospital_id", "case_id", "status"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(
            f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" '
            "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
            "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
        ))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
