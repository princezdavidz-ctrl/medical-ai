"""Add compliance control assessments and access review campaigns."""
from alembic import op
import sqlalchemy as sa

revision = "0050_access_reviews_controls"
down_revision = "0049_compliance_security"
branch_labels = None
depends_on = None

TABLES = ("compliance_controls", "compliance_control_assessments", "access_review_campaigns", "access_review_items")


def upgrade() -> None:
    op.create_table(
        "compliance_controls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("framework", sa.String(24), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_requirements", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "owner_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_compliance_control_owner"),
        sa.UniqueConstraint("hospital_id", "code", "version", name="uq_compliance_control_version"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_compliance_control_hospital_id"),
        sa.CheckConstraint("version >= 1", name="ck_compliance_control_version"),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_compliance_control_status"),
        sa.CheckConstraint("length(trim(code)) BETWEEN 2 AND 80", name="ck_compliance_control_code"),
        sa.CheckConstraint("framework IN ('kenya_dpa', 'hipaa', 'iso27001', 'iso27799', 'gdpr', 'internal', 'other')", name="ck_compliance_control_framework"),
    )
    op.create_index("ix_compliance_control_status", "compliance_controls", ["hospital_id", "status", "framework"])

    op.create_table(
        "compliance_control_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("control_id", sa.Uuid(), nullable=False),
        sa.Column("assessor_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.String(80)),
        sa.Column("assessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["hospital_id", "control_id"], ["compliance_controls.hospital_id", "compliance_controls.id"], name="fk_control_assessment_control"),
        sa.ForeignKeyConstraint(["hospital_id", "assessor_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_control_assessment_assessor"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_control_assessment_reviewer"),
        sa.CheckConstraint("status IN ('pending_review', 'compliant', 'partially_compliant', 'non_compliant', 'not_applicable')", name="ck_control_assessment_status"),
        sa.CheckConstraint("evidence_reference IS NULL OR evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_control_assessment_evidence"),
        sa.CheckConstraint("next_review_at IS NULL OR next_review_at > assessed_at", name="ck_control_assessment_next_review"),
        sa.CheckConstraint("(status = 'pending_review' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) OR (status != 'pending_review' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_control_assessment_review_state"),
    )
    op.create_index("ix_control_assessment_history", "compliance_control_assessments", ["hospital_id", "control_id", "assessed_at"])

    op.create_table(
        "access_review_campaigns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "id", name="uq_access_review_campaign_hospital_id"),
        sa.CheckConstraint("status IN ('draft', 'open', 'completed', 'cancelled')", name="ck_access_review_campaign_status"),
        sa.CheckConstraint("period_end > period_start", name="ck_access_review_campaign_period"),
        sa.CheckConstraint("completed_at IS NULL OR status = 'completed'", name="ck_access_review_campaign_completion"),
    )
    op.create_index("ix_access_review_campaign_status", "access_review_campaigns", ["hospital_id", "status", "due_at"])

    op.create_table(
        "access_review_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("subject_user_id", sa.Uuid(), nullable=False),
        sa.Column("role_name_snapshot", sa.String(80), nullable=False),
        sa.Column("department_id", sa.Uuid()),
        sa.Column("decision", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("justification", sa.Text()),
        sa.Column("review_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by_user_id", sa.Uuid()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "campaign_id"], ["access_review_campaigns.hospital_id", "access_review_campaigns.id"], name="fk_access_review_item_campaign"),
        sa.ForeignKeyConstraint(["hospital_id", "subject_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_access_review_item_subject"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_access_review_item_reviewer"),
        sa.ForeignKeyConstraint(["hospital_id", "approved_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_access_review_item_approver"),
        sa.UniqueConstraint("hospital_id", "campaign_id", "subject_user_id", name="uq_access_review_campaign_subject"),
        sa.CheckConstraint("decision IN ('pending', 'keep', 'change', 'revoke')", name="ck_access_review_item_decision"),
        sa.CheckConstraint("review_status IN ('pending', 'awaiting_approval', 'approved')", name="ck_access_review_item_status"),
        sa.CheckConstraint("(review_status = 'pending' AND decision = 'pending' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND approved_by_user_id IS NULL AND approved_at IS NULL) OR (review_status = 'awaiting_approval' AND decision IN ('keep', 'change', 'revoke') AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND approved_by_user_id IS NULL AND approved_at IS NULL) OR (review_status = 'approved' AND decision IN ('keep', 'change', 'revoke') AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)", name="ck_access_review_item_workflow"),
    )
    op.create_index("ix_access_review_item_subject", "access_review_items", ["hospital_id", "subject_user_id", "review_status"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
