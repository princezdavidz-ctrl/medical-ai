"""Add clinician-bound AI session context and review records."""
from alembic import op
import sqlalchemy as sa

revision = "0053_ai_clinical_assistant"
down_revision = "0052_hospital_reporting"
branch_labels = None
depends_on = None

TABLES = ("clinical_ai_session_contexts", "ai_clinical_review_records")


def upgrade() -> None:
    op.create_table(
        "clinical_ai_session_contexts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("consent_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), sa.ForeignKey("patient_care_assignments.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["session_id", "hospital_id", "owner_user_id"], ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"], name="fk_clinical_ai_context_session_owner"),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_clinical_ai_context_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_clinical_ai_context_encounter"),
        sa.ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_clinical_ai_context_consent"),
        sa.UniqueConstraint("hospital_id", "session_id", name="uq_clinical_ai_context_session"),
        sa.CheckConstraint("status IN ('active', 'revoked', 'expired')", name="ck_clinical_ai_context_status"),
    )
    op.create_index("ix_clinical_ai_context_patient", "clinical_ai_session_contexts", ["hospital_id", "patient_id", "encounter_id"])

    op.create_table(
        "ai_clinical_review_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("assistant_sequence", sa.Integer(), nullable=False),
        sa.Column("response_digest", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("note_reference", sa.String(80)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id", "hospital_id", "owner_user_id"], ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"], name="fk_ai_clinical_review_session_owner"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_ai_clinical_review_reviewer"),
        sa.UniqueConstraint("hospital_id", "session_id", "assistant_sequence", name="uq_ai_clinical_review_sequence"),
        sa.CheckConstraint("decision IN ('accepted_for_consideration', 'rejected', 'needs_revision')", name="ck_ai_clinical_review_decision"),
        sa.CheckConstraint("assistant_sequence > 0", name="ck_ai_clinical_review_sequence"),
        sa.CheckConstraint("response_digest ~ '^[0-9a-f]{64}$'", name="ck_ai_clinical_review_digest"),
        sa.CheckConstraint("note_reference IS NULL OR note_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_ai_clinical_review_note_ref"),
    )
    op.create_index("ix_ai_clinical_review_patient", "ai_clinical_review_records", ["hospital_id", "patient_id", "reviewed_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))

    op.execute("""
        CREATE FUNCTION prevent_ai_clinical_review_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'AI clinical review records are append-only';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_ai_clinical_reviews_immutable BEFORE UPDATE OR DELETE ON ai_clinical_review_records FOR EACH ROW EXECUTE FUNCTION prevent_ai_clinical_review_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_ai_clinical_reviews_immutable ON ai_clinical_review_records")
    op.execute("DROP FUNCTION IF EXISTS prevent_ai_clinical_review_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
