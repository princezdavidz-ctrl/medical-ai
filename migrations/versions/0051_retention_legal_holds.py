"""Add retention policies, legal holds and disposition approvals."""
from alembic import op
import sqlalchemy as sa

revision = "0051_retention_legal_holds"
down_revision = "0050_access_reviews_controls"
branch_labels = None
depends_on = None

TABLES = ("retention_policies", "legal_holds", "retention_disposition_requests")


def upgrade() -> None:
    op.create_table(
        "retention_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("policy_code", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("data_domain", sa.String(24), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("legal_basis", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("effective_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "approved_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_retention_policy_approver"),
        sa.UniqueConstraint("hospital_id", "policy_code", "version", name="uq_retention_policy_version"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_retention_policy_hospital_id"),
        sa.CheckConstraint("data_domain IN ('clinical_records', 'billing_records', 'audit_logs', 'communications', 'security_logs', 'hr_records', 'other')", name="ck_retention_policy_domain"),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_retention_policy_status"),
        sa.CheckConstraint("retention_days BETWEEN 1 AND 36500", name="ck_retention_policy_days"),
        sa.CheckConstraint("(status = 'active' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL AND effective_at IS NOT NULL) OR (status != 'active' AND approved_by_user_id IS NULL AND approved_at IS NULL)", name="ck_retention_policy_approval"),
    )
    op.create_index("ix_retention_policy_domain", "retention_policies", ["hospital_id", "data_domain", "status"])

    op.create_table(
        "legal_holds",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("hold_reference", sa.String(80), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("issued_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("released_by_user_id", sa.Uuid()),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("release_reason", sa.Text()),
        sa.ForeignKeyConstraint(["hospital_id", "issued_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_legal_hold_issuer"),
        sa.ForeignKeyConstraint(["hospital_id", "released_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_legal_hold_releaser"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_legal_hold_hospital_id"),
        sa.UniqueConstraint("hospital_id", "hold_reference", name="uq_legal_hold_reference"),
        sa.CheckConstraint("status IN ('active', 'released', 'expired')", name="ck_legal_hold_status"),
        sa.CheckConstraint("json_typeof(scope) = 'object'", name="ck_legal_hold_scope_object"),
        sa.CheckConstraint("(status = 'released' AND released_by_user_id IS NOT NULL AND released_at IS NOT NULL AND release_reason IS NOT NULL) OR (status != 'released' AND released_by_user_id IS NULL AND released_at IS NULL AND release_reason IS NULL)", name="ck_legal_hold_release_state"),
    )
    op.create_index("ix_legal_hold_status", "legal_holds", ["hospital_id", "status", "expires_at"])

    op.create_table(
        "retention_disposition_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_reference", sa.String(80), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("eligible_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "policy_id"], ["retention_policies.hospital_id", "retention_policies.id"], name="fk_retention_disposition_policy"),
        sa.ForeignKeyConstraint(["hospital_id", "requested_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_retention_disposition_requester"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_retention_disposition_reviewer"),
        sa.CheckConstraint("action IN ('archive', 'delete')", name="ck_retention_disposition_action"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'blocked_by_legal_hold')", name="ck_retention_disposition_status"),
        sa.CheckConstraint("resource_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_retention_disposition_resource_ref"),
        sa.CheckConstraint("(status = 'pending' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) OR (status IN ('approved', 'rejected', 'blocked_by_legal_hold') AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_retention_disposition_review_state"),
    )
    op.create_index("ix_retention_disposition_queue", "retention_disposition_requests", ["hospital_id", "status", "eligible_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
