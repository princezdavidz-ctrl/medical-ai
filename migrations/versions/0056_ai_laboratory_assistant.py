"""Add patient-bound AI laboratory interpretation review cases."""
from alembic import op
import sqlalchemy as sa

revision = "0056_ai_laboratory_assistant"
down_revision = "0055_ai_diagnostic_support"
branch_labels = None
depends_on = None

TABLE = "ai_laboratory_interpretation_cases"


def upgrade() -> None:
    op.create_table(
        TABLE,
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
        sa.Column("laboratory_result_ids", sa.JSON(), nullable=False),
        sa.Column("result_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_citation_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("review_decision", sa.String(40)),
        sa.Column("review_note_reference", sa.String(80)),
        sa.Column("review_reference", sa.String(80)),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id", "hospital_id", "owner_user_id"], ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"], name="fk_ai_lab_case_session_owner"),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_ai_lab_case_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_ai_lab_case_encounter"),
        sa.ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_ai_lab_case_consent"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_ai_lab_case_reviewer"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_ai_lab_case_hospital_id"),
        sa.UniqueConstraint("hospital_id", "session_id", "source_assistant_sequence", name="uq_ai_lab_case_source"),
        sa.CheckConstraint("source_assistant_sequence > 0", name="ck_ai_lab_case_sequence"),
        sa.CheckConstraint("source_response_digest ~ '^[0-9a-f]{64}$'", name="ck_ai_lab_case_digest"),
        sa.CheckConstraint("json_typeof(laboratory_result_ids) = 'array' AND json_array_length(laboratory_result_ids) > 0", name="ck_ai_lab_case_result_ids"),
        sa.CheckConstraint("json_typeof(result_snapshot) = 'array' AND json_array_length(result_snapshot) > 0", name="ck_ai_lab_case_snapshot"),
        sa.CheckConstraint("json_typeof(evidence_citation_ids) = 'array'", name="ck_ai_lab_case_citations"),
        sa.CheckConstraint("review_decision IS NULL OR review_decision IN ('accepted_for_clinical_consideration', 'needs_correction', 'not_applicable')", name="ck_ai_lab_case_review_decision"),
        sa.CheckConstraint("status IN ('pending_review', 'reviewed')", name="ck_ai_lab_case_status"),
        sa.CheckConstraint("review_reference IS NULL OR review_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_ai_lab_case_review_reference"),
        sa.CheckConstraint("review_note_reference IS NULL OR review_note_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_ai_lab_case_note_reference"),
        sa.CheckConstraint(
            "(status = 'pending_review' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND review_decision IS NULL) OR "
            "(status = 'reviewed' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND review_decision IS NOT NULL)",
            name="ck_ai_lab_case_review_state",
        ),
    )
    op.create_index("ix_ai_lab_case_patient_created", TABLE, ["hospital_id", "patient_id", "created_at"])
    op.execute(sa.text(f'ALTER TABLE "{TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(
        f'CREATE POLICY "{TABLE}_hospital_isolation" ON "{TABLE}" '
        "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
        "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
    ))


def downgrade() -> None:
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{TABLE}_hospital_isolation" ON "{TABLE}"'))
    op.execute(sa.text(f'ALTER TABLE "{TABLE}" DISABLE ROW LEVEL SECURITY'))
    op.drop_table(TABLE)
