"""Add hospital-scoped central AI emergency pause controls."""

from alembic import op
import sqlalchemy as sa

revision = "0014_ai_hospital_controls"
down_revision = "0013_ai_eval_prompt_digest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_hospital_controls",
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), primary_key=True),
        sa.Column("ai_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pause_reason", sa.Text()),
        sa.Column("changed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("ALTER TABLE ai_hospital_controls ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ai_hospital_controls FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY hospital_tenant_isolation ON ai_hospital_controls "
        "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
        "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS hospital_tenant_isolation ON ai_hospital_controls")
    op.execute("ALTER TABLE ai_hospital_controls NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ai_hospital_controls DISABLE ROW LEVEL SECURITY")
    op.drop_table("ai_hospital_controls")
