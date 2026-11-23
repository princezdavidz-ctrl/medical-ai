"""Persist AI evaluation datasets, runs, approvals and release governance."""
from alembic import op
import sqlalchemy as sa

revision = "0008_ai_evaluation_governance"
down_revision = "0007_knowledge_intake_write_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_evaluation_datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_key", sa.String(120), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("license_reference", sa.String(500), nullable=False),
        sa.Column("submitted_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("dataset_key", "version", name="uq_ai_eval_dataset_key_version"),
        sa.CheckConstraint("classification IN ('synthetic', 'deidentified')", name="ck_ai_eval_dataset_classification"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'revoked', 'retired')", name="ck_ai_eval_dataset_status"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="ck_ai_eval_dataset_sha256"),
    )
    op.create_index("ix_ai_eval_dataset_status", "ai_evaluation_datasets", ["status"])

    op.create_table(
        "ai_evaluation_threshold_sets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("operating_mode", sa.String(24), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("minimums_json", sa.JSON(), nullable=False),
        sa.Column("hard_stop_rules_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("capability", "operating_mode", "version", name="uq_ai_eval_threshold_version"),
        sa.CheckConstraint("operating_mode IN ('hybrid', 'offline', 'degraded')", name="ck_ai_eval_threshold_mode"),
        sa.CheckConstraint("status IN ('draft', 'approved', 'retired', 'revoked')", name="ck_ai_eval_threshold_status"),
    )
    op.create_index("ix_ai_eval_threshold_lookup", "ai_evaluation_threshold_sets", ["capability", "operating_mode", "status"])

    op.create_table(
        "ai_evaluation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("operating_mode", sa.String(24), nullable=False),
        sa.Column("provider_id", sa.String(100), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("model_version", sa.String(120), nullable=False),
        sa.Column("model_sha256", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(120), nullable=False),
        sa.Column("evaluator_version", sa.String(120), nullable=False),
        sa.Column("evaluator_sha256", sa.String(64), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("ai_evaluation_datasets.id"), nullable=False),
        sa.Column("threshold_set_id", sa.Uuid(), sa.ForeignKey("ai_evaluation_threshold_sets.id"), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("failures_json", sa.JSON(), nullable=False),
        sa.Column("result_sha256", sa.String(64)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('queued', 'running', 'passed', 'failed', 'aborted')", name="ck_ai_eval_run_status"),
        sa.CheckConstraint("model_sha256 ~ '^[0-9a-f]{64}$'", name="ck_ai_eval_run_model_sha256"),
        sa.CheckConstraint("evaluator_sha256 ~ '^[0-9a-f]{64}$'", name="ck_ai_eval_run_evaluator_sha256"),
        sa.CheckConstraint("result_sha256 IS NULL OR result_sha256 ~ '^[0-9a-f]{64}$'", name="ck_ai_eval_run_result_sha256"),
    )
    op.create_index("ix_ai_eval_run_capability_mode_created", "ai_evaluation_runs", ["capability", "operating_mode", "created_at"])
    op.create_index("ix_ai_eval_run_dataset", "ai_evaluation_runs", ["dataset_id"])

    op.create_table(
        "ai_model_releases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("release_key", sa.String(120), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), sa.ForeignKey("ai_evaluation_runs.id"), nullable=False),
        sa.Column("threshold_set_id", sa.Uuid(), sa.ForeignKey("ai_evaluation_threshold_sets.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("previous_approved_release_id", sa.Uuid(), sa.ForeignKey("ai_model_releases.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("release_key", name="uq_ai_model_release_key"),
        sa.CheckConstraint("status IN ('draft', 'approved', 'active', 'revoked', 'expired', 'rolled_back')", name="ck_ai_model_release_status"),
    )
    op.create_index("ix_ai_model_release_status_expiry", "ai_model_releases", ["status", "expires_at"])

    op.create_table(
        "ai_release_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("release_id", sa.Uuid(), sa.ForeignKey("ai_model_releases.id"), nullable=False),
        sa.Column("approval_role", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("credential_reference", sa.String(500), nullable=False),
        sa.Column("credential_verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("release_id", "approval_role", name="uq_ai_release_approval_role"),
        sa.CheckConstraint("approval_role IN ('clinical_safety_owner', 'clinical_reviewer')", name="ck_ai_release_approval_role"),
        sa.CheckConstraint("actor_user_id <> credential_verified_by_user_id", name="ck_ai_release_credential_verifier_other"),
    )
    op.create_index("ix_ai_release_approval_actor", "ai_release_approvals", ["actor_user_id", "release_id"])

    op.create_table(
        "ai_governance_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("outcome IN ('accepted', 'rejected', 'revoked', 'activated', 'rolled_back')", name="ck_ai_governance_event_outcome"),
    )
    op.create_index("ix_ai_governance_event_resource_time", "ai_governance_events", ["resource_type", "resource_id", "occurred_at"])

    # A separately provisioned DB role is required; ordinary tenant sessions have no policy.
    tables = (
        "ai_evaluation_datasets", "ai_evaluation_threshold_sets", "ai_evaluation_runs",
        "ai_model_releases", "ai_release_approvals", "ai_governance_events",
    )
    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_worker_only ON {table} "
            "USING (current_user = 'medical_ai_governance_worker') "
            "WITH CHECK (current_user = 'medical_ai_governance_worker')"
        )

    op.execute("""
        CREATE FUNCTION prevent_ai_governance_event_mutation()
        RETURNS trigger AS $fn$
        BEGIN
            RAISE EXCEPTION 'AI governance events are append-only';
        END;
        $fn$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER ai_governance_events_append_only
        BEFORE UPDATE OR DELETE ON ai_governance_events
        FOR EACH ROW EXECUTE FUNCTION prevent_ai_governance_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ai_governance_events_append_only ON ai_governance_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_ai_governance_event_mutation()")
    tables = (
        "ai_evaluation_datasets", "ai_evaluation_threshold_sets", "ai_evaluation_runs",
        "ai_model_releases", "ai_release_approvals", "ai_governance_events",
    )
    for table in tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_worker_only ON {table}")
    op.drop_index("ix_ai_governance_event_resource_time", table_name="ai_governance_events")
    op.drop_table("ai_governance_events")
    op.drop_index("ix_ai_release_approval_actor", table_name="ai_release_approvals")
    op.drop_table("ai_release_approvals")
    op.drop_index("ix_ai_model_release_status_expiry", table_name="ai_model_releases")
    op.drop_table("ai_model_releases")
    op.drop_index("ix_ai_eval_run_dataset", table_name="ai_evaluation_runs")
    op.drop_index("ix_ai_eval_run_capability_mode_created", table_name="ai_evaluation_runs")
    op.drop_table("ai_evaluation_runs")
    op.drop_index("ix_ai_eval_threshold_lookup", table_name="ai_evaluation_threshold_sets")
    op.drop_table("ai_evaluation_threshold_sets")
    op.drop_index("ix_ai_eval_dataset_status", table_name="ai_evaluation_datasets")
    op.drop_table("ai_evaluation_datasets")
