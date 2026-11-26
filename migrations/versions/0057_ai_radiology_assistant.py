"""Add patient-bound AI radiology interpretation review cases."""
from alembic import op
import sqlalchemy as sa

revision = "0057_ai_radiology_assistant"
down_revision = "0056_ai_laboratory_assistant"
branch_labels = None
depends_on = None

TABLE = "ai_radiology_interpretation_cases"


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
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("report_digest", sa.String(64), nullable=False),
        sa.Column("report_snapshot", sa.JSON(), nullable=False),
        sa.Column("source_assistant_sequence", sa.Integer(), nullable=False),
        sa.Column("source_response_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("review_decision", sa.String(32)),
        sa.Column("review_reference", sa.String(80)),
        sa.Column("review_note_reference", sa.String(80)),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id", "hospital_id", "owner_user_id"], ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"], name="fk_ai_radiology_case_session_owner"),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_ai_radiology_case_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_ai_radiology_case_encounter"),
        sa.ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_ai_radiology_case_consent"),
        sa.ForeignKeyConstraint(["hospital_id", "report_id"], ["imaging_reports.hospital_id", "imaging_reports.id"], name="fk_ai_radiology_case_report"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_ai_radiology_case_reviewer"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_ai_radiology_case_hospital_id"),
        sa.UniqueConstraint("hospital_id", "session_id", "source_assistant_sequence", name="uq_ai_radiology_case_source"),
        sa.CheckConstraint("source_assistant_sequence > 0", name="ck_ai_radiology_case_sequence"),
        sa.CheckConstraint("report_digest ~ '^[0-9a-f]{64}$'", name="ck_ai_radiology_case_report_digest"),
        sa.CheckConstraint("source_response_digest ~ '^[0-9a-f]{64}$'", name="ck_ai_radiology_case_response_digest"),
        sa.CheckConstraint("json_typeof(report_snapshot) = 'object'", name="ck_ai_radiology_case_snapshot"),
        sa.CheckConstraint("status IN ('pending_review', 'reviewed', 'stale')", name="ck_ai_radiology_case_status"),
        sa.CheckConstraint("review_reference IS NULL OR review_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_ai_radiology_case_review_reference"),
        sa.CheckConstraint("review_note_reference IS NULL OR review_note_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_ai_radiology_case_note_reference"),
        sa.CheckConstraint(
            "(status = 'pending_review' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND review_decision IS NULL) OR "
            "(status IN ('reviewed', 'stale') AND ((reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND review_decision IS NULL) OR "
            "(reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND review_decision IS NOT NULL)))",
            name="ck_ai_radiology_case_review_state",
        ),
    )
    op.create_index("ix_ai_radiology_case_patient_created", TABLE, ["hospital_id", "patient_id", "created_at"])
    op.execute(sa.text(f'ALTER TABLE "{TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(
        f'CREATE POLICY "{TABLE}_hospital_isolation" ON "{TABLE}" '
        "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
        "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
    ))


def downgrade() -> None:
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{TABLE}_hospital_isolation" ON "{TABLE}"'))
    op.execute(sa.text(f'ALTER TABLE "{TABLE}" DISABLE ROW LEVEL SECURITY'))
    op.drop_table(TABLE)
