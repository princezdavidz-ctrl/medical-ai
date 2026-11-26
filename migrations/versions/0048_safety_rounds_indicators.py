"""Add safety rounds and quality indicator reporting."""
from alembic import op
import sqlalchemy as sa

revision = "0048_safety_rounds_indicators"
down_revision = "0047_quality_patient_safety"
branch_labels = None
depends_on = None

TABLES = ("safety_rounds", "safety_round_findings", "quality_indicator_definitions", "quality_indicator_measurements")


def upgrade() -> None:
    op.create_table(
        "safety_rounds",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Uuid()),
        sa.Column("lead_user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("conducted_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("summary", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_safety_round_department"),
        sa.ForeignKeyConstraint(["hospital_id", "lead_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_round_lead"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_safety_round_hospital_id"),
        sa.CheckConstraint("status IN ('planned', 'in_progress', 'completed', 'cancelled')", name="ck_safety_round_status"),
        sa.CheckConstraint("completed_at IS NULL OR conducted_at IS NOT NULL", name="ck_safety_round_completion"),
    )
    op.create_index("ix_safety_round_department_schedule", "safety_rounds", ["hospital_id", "department_id", "scheduled_at", "status"])

    op.create_table(
        "safety_round_findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("resolution_note", sa.Text()),
        sa.Column("resolved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "round_id"], ["safety_rounds.hospital_id", "safety_rounds.id"], name="fk_safety_round_finding_round"),
        sa.ForeignKeyConstraint(["hospital_id", "owner_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_round_finding_owner"),
        sa.CheckConstraint("severity IN ('low', 'moderate', 'high', 'critical')", name="ck_safety_round_finding_severity"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'resolved', 'accepted_risk')", name="ck_safety_round_finding_status"),
        sa.CheckConstraint("length(trim(description)) BETWEEN 10 AND 3000", name="ck_safety_round_finding_description"),
        sa.CheckConstraint("(status = 'resolved' AND resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL) OR (status != 'resolved' AND resolved_at IS NULL AND resolved_by_user_id IS NULL)", name="ck_safety_round_finding_resolution"),
    )
    op.create_index("ix_safety_round_finding_owner", "safety_round_findings", ["hospital_id", "owner_user_id", "status", "due_at"])

    op.create_table(
        "quality_indicator_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False, server_default="rate"),
        sa.Column("numerator_definition", sa.Text(), nullable=False),
        sa.Column("denominator_definition", sa.Text(), nullable=False),
        sa.Column("aggregation_period", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "code", "version", name="uq_quality_indicator_code_version"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_quality_indicator_hospital_id"),
        sa.CheckConstraint("version >= 1", name="ck_quality_indicator_version"),
        sa.CheckConstraint("aggregation_period IN ('daily', 'weekly', 'monthly', 'quarterly', 'annual')", name="ck_quality_indicator_period"),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_quality_indicator_status"),
        sa.CheckConstraint("length(trim(code)) BETWEEN 2 AND 80", name="ck_quality_indicator_code"),
        sa.CheckConstraint("length(trim(name)) BETWEEN 2 AND 180", name="ck_quality_indicator_name"),
    )
    op.create_index("ix_quality_indicator_status", "quality_indicator_definitions", ["hospital_id", "status", "code"])

    op.create_table(
        "quality_indicator_measurements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("indicator_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("numerator", sa.Integer(), nullable=False),
        sa.Column("denominator", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(16, 6), nullable=False),
        sa.Column("data_source", sa.String(120), nullable=False),
        sa.Column("source_version", sa.String(80), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "indicator_id"], ["quality_indicator_definitions.hospital_id", "quality_indicator_definitions.id"], name="fk_quality_measurement_indicator"),
        sa.CheckConstraint("numerator >= 0 AND denominator > 0 AND value >= 0", name="ck_quality_measurement_values"),
        sa.CheckConstraint("period_end > period_start", name="ck_quality_measurement_period"),
        sa.UniqueConstraint("hospital_id", "indicator_id", "period_start", "period_end", name="uq_quality_measurement_period"),
    )
    op.create_index("ix_quality_measurement_period", "quality_indicator_measurements", ["hospital_id", "indicator_id", "period_start", "period_end"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
