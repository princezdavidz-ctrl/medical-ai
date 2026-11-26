"""Add governed report catalog, report runs and export metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0052_hospital_reporting"
down_revision = "0051_retention_legal_holds"
branch_labels = None
depends_on = None

TABLES = ("report_definitions", "report_runs", "report_export_jobs")


def upgrade() -> None:
    op.create_table(
        "report_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("report_code", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("report_key", sa.String(40), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("data_domain", sa.String(24), nullable=False),
        sa.Column("required_roles", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("department_scoped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("definition", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "report_code", "version", name="uq_report_definition_version"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_report_definition_hospital_id"),
        sa.CheckConstraint("report_key IN ('patient_flow', 'bed_occupancy', 'emergency_volume', 'billing_summary', 'quality_safety', 'compliance_overview')", name="ck_report_definition_key"),
        sa.CheckConstraint("data_domain IN ('clinical', 'operations', 'finance', 'quality', 'compliance')", name="ck_report_definition_domain"),
        sa.CheckConstraint("status IN ('draft', 'published', 'retired')", name="ck_report_definition_status"),
        sa.CheckConstraint("version >= 1", name="ck_report_definition_version"),
        sa.CheckConstraint("json_typeof(required_roles) = 'array'", name="ck_report_definition_roles"),
        sa.CheckConstraint("(status = 'published' AND published_by_user_id IS NOT NULL AND published_at IS NOT NULL) OR (status != 'published' AND published_by_user_id IS NULL AND published_at IS NULL)", name="ck_report_definition_publish_state"),
    )
    op.create_index("ix_report_definition_catalog", "report_definitions", ["hospital_id", "data_domain", "status"])

    op.create_table(
        "report_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("result_summary", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("source_versions", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "definition_id"], ["report_definitions.hospital_id", "report_definitions.id"], name="fk_report_run_definition"),
        sa.CheckConstraint("status IN ('completed', 'failed', 'expired')", name="ck_report_run_status"),
        sa.CheckConstraint("expires_at > generated_at", name="ck_report_run_expiry"),
    )
    op.create_index("ix_report_run_history", "report_runs", ["hospital_id", "requested_by_user_id", "generated_at"])

    op.create_table(
        "report_export_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("output_reference", sa.String(80)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "run_id"], ["report_runs.hospital_id", "report_runs.id"], name="fk_report_export_run"),
        sa.CheckConstraint("format IN ('csv', 'pdf')", name="ck_report_export_format"),
        sa.CheckConstraint("status IN ('queued', 'processing', 'completed', 'failed', 'expired')", name="ck_report_export_status"),
        sa.CheckConstraint("output_reference IS NULL OR output_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_report_export_reference"),
    )
    op.create_index("ix_report_export_queue", "report_export_jobs", ["hospital_id", "status", "created_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))

    op.execute("""
        CREATE FUNCTION prevent_published_report_definition_mutation() RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'published' THEN
                RAISE EXCEPTION 'published report definitions are immutable; create a new version';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_report_definition_versioned BEFORE UPDATE OR DELETE ON report_definitions FOR EACH ROW EXECUTE FUNCTION prevent_published_report_definition_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_report_definition_versioned ON report_definitions")
    op.execute("DROP FUNCTION IF EXISTS prevent_published_report_definition_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
