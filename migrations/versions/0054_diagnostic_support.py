"""Add clinician-reviewed diagnostic support cases and suggestions."""
from alembic import op
import sqlalchemy as sa

revision = "0054_diagnostic_support"
down_revision = "0053_ai_clinical_assistant"
branch_labels = None
depends_on = None

TABLES = ("diagnostic_support_cases", "diagnostic_differentials", "diagnostic_test_considerations")


def upgrade() -> None:
    op.create_table(
        "diagnostic_support_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("problem_representation", sa.Text(), nullable=False),
        sa.Column("known_findings", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("missing_information", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("red_flags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("clinician_assessment", sa.Text()),
        sa.Column("closed_by_user_id", sa.Uuid()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_diagnostic_case_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_diagnostic_case_encounter"),
        sa.ForeignKeyConstraint(["hospital_id", "session_id"], ["clinical_ai_session_contexts.hospital_id", "clinical_ai_session_contexts.session_id"], name="fk_diagnostic_case_ai_session"),
        sa.ForeignKeyConstraint(["hospital_id", "created_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_case_creator"),
        sa.ForeignKeyConstraint(["hospital_id", "closed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_case_closer"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_diagnostic_case_hospital_id"),
        sa.CheckConstraint("status IN ('open', 'under_review', 'closed')", name="ck_diagnostic_case_status"),
        sa.CheckConstraint("length(trim(problem_representation)) BETWEEN 10 AND 4000", name="ck_diagnostic_case_problem"),
        sa.CheckConstraint("status != 'closed' OR (clinician_assessment IS NOT NULL AND closed_by_user_id IS NOT NULL AND closed_at IS NOT NULL)", name="ck_diagnostic_case_closure"),
    )
    op.create_index("ix_diagnostic_case_patient", "diagnostic_support_cases", ["hospital_id", "patient_id", "created_at"])
    op.create_index("ix_diagnostic_case_encounter", "diagnostic_support_cases", ["hospital_id", "encounter_id", "status"])

    op.create_table(
        "diagnostic_differentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("concept_code", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(180), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_sequence", sa.Integer(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("evidence_citation_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(24), nullable=False, server_default="proposed"),
        sa.Column("entered_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("review_note", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "case_id"], ["diagnostic_support_cases.hospital_id", "diagnostic_support_cases.id"], name="fk_diagnostic_differential_case"),
        sa.ForeignKeyConstraint(["hospital_id", "entered_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_differential_author"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_differential_reviewer"),
        sa.UniqueConstraint("hospital_id", "case_id", "concept_code", name="uq_diagnostic_differential_concept"),
        sa.CheckConstraint("status IN ('proposed', 'considered', 'ruled_out', 'clinician_confirmed')", name="ck_diagnostic_differential_status"),
        sa.CheckConstraint("source_sequence > 0", name="ck_diagnostic_differential_sequence"),
        sa.CheckConstraint("source_digest ~ '^[0-9a-f]{64}$'", name="ck_diagnostic_differential_digest"),
        sa.CheckConstraint("length(trim(display_name)) BETWEEN 2 AND 180", name="ck_diagnostic_differential_name"),
    )
    op.create_index("ix_diagnostic_differential_case", "diagnostic_differentials", ["hospital_id", "case_id", "status"])

    op.create_table(
        "diagnostic_test_considerations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("test_code", sa.String(80), nullable=False),
        sa.Column("test_name", sa.String(180), nullable=False),
        sa.Column("modality", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(24), nullable=False, server_default="routine"),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_sequence", sa.Integer(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("evidence_citation_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.Column("entered_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("review_note", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "case_id"], ["diagnostic_support_cases.hospital_id", "diagnostic_support_cases.id"], name="fk_diagnostic_test_case"),
        sa.ForeignKeyConstraint(["hospital_id", "entered_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_test_author"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_diagnostic_test_reviewer"),
        sa.UniqueConstraint("hospital_id", "case_id", "test_code", "modality", name="uq_diagnostic_test_consideration"),
        sa.CheckConstraint("modality IN ('laboratory', 'imaging', 'procedure', 'other')", name="ck_diagnostic_test_modality"),
        sa.CheckConstraint("priority IN ('routine', 'urgent', 'stat_consideration')", name="ck_diagnostic_test_priority"),
        sa.CheckConstraint("status IN ('proposed', 'considered', 'declined')", name="ck_diagnostic_test_status"),
        sa.CheckConstraint("source_sequence > 0", name="ck_diagnostic_test_sequence"),
        sa.CheckConstraint("source_digest ~ '^[0-9a-f]{64}$'", name="ck_diagnostic_test_digest"),
        sa.CheckConstraint("length(trim(test_name)) BETWEEN 2 AND 180", name="ck_diagnostic_test_name"),
    )
    op.create_index("ix_diagnostic_test_case", "diagnostic_test_considerations", ["hospital_id", "case_id", "status"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid'))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
