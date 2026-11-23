"""Add tenant-scoped AI subscription quotas, reservations and usage ledger."""
from alembic import op
import sqlalchemy as sa

revision = "0012_ai_usage_accounting"
down_revision = "0011_ai_conversation_sessions"
branch_labels = None
depends_on = None

TABLES = (
    "ai_usage_policies",
    "ai_usage_counters",
    "ai_usage_reservations",
    "ai_usage_events",
)


def upgrade() -> None:
    op.create_table(
        "ai_usage_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("subscription_reference", sa.String(160), nullable=False),
        sa.Column("plan_code", sa.String(80), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("request_limit", sa.BigInteger(), nullable=False),
        sa.Column("input_token_limit", sa.BigInteger(), nullable=False),
        sa.Column("output_token_limit", sa.BigInteger(), nullable=False),
        sa.Column("max_output_tokens_per_request", sa.Integer(), nullable=False),
        sa.Column("cost_limit_micros", sa.BigInteger()),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "period_start", "period_end", name="uq_ai_usage_policy_period"),
        sa.CheckConstraint("period_end > period_start", name="ck_ai_usage_policy_period"),
        sa.CheckConstraint("request_limit > 0", name="ck_ai_usage_policy_request_limit"),
        sa.CheckConstraint("input_token_limit > 0", name="ck_ai_usage_policy_input_limit"),
        sa.CheckConstraint("output_token_limit > 0", name="ck_ai_usage_policy_output_limit"),
        sa.CheckConstraint("max_output_tokens_per_request > 0", name="ck_ai_usage_policy_max_output"),
        sa.CheckConstraint("cost_limit_micros IS NULL OR cost_limit_micros >= 0", name="ck_ai_usage_policy_cost_limit"),
        sa.CheckConstraint("status IN ('active', 'suspended', 'expired')", name="ck_ai_usage_policy_status"),
    )
    op.create_index("ix_ai_usage_policy_hospital_status", "ai_usage_policies", ["hospital_id", "status", "period_start", "period_end"])

    op.create_table(
        "ai_usage_counters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("policy_id", sa.Uuid(), sa.ForeignKey("ai_usage_policies.id"), nullable=False),
        sa.Column("requests_used", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("requests_reserved", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("input_tokens_used", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("input_tokens_reserved", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens_used", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens_reserved", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_micros_used", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_micros_reserved", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "policy_id", name="uq_ai_usage_counter_policy"),
        sa.CheckConstraint("requests_used >= 0 AND requests_reserved >= 0", name="ck_ai_usage_counter_requests"),
        sa.CheckConstraint("input_tokens_used >= 0 AND input_tokens_reserved >= 0", name="ck_ai_usage_counter_input"),
        sa.CheckConstraint("output_tokens_used >= 0 AND output_tokens_reserved >= 0", name="ck_ai_usage_counter_output"),
        sa.CheckConstraint("cost_micros_used >= 0 AND cost_micros_reserved >= 0", name="ck_ai_usage_counter_cost"),
    )
    op.create_index("ix_ai_usage_counter_hospital", "ai_usage_counters", ["hospital_id", "policy_id"])

    op.create_table(
        "ai_usage_reservations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("policy_id", sa.Uuid(), sa.ForeignKey("ai_usage_policies.id"), nullable=False),
        sa.Column("counter_id", sa.Uuid(), sa.ForeignKey("ai_usage_counters.id"), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("operating_mode", sa.String(24), nullable=False),
        sa.Column("provider_class", sa.String(24), nullable=False),
        sa.Column("provider_id", sa.String(120), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("reserved_input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("reserved_output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("estimated_cost_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("pricing_snapshot_json", sa.JSON()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("hospital_id", "idempotency_key", name="uq_ai_usage_reservation_idempotency"),
        sa.CheckConstraint("status IN ('reserved', 'settled', 'released')", name="ck_ai_usage_reservation_status"),
        sa.CheckConstraint("reserved_input_tokens >= 0 AND reserved_output_tokens >= 0", name="ck_ai_usage_reservation_tokens"),
        sa.CheckConstraint("estimated_cost_micros >= 0", name="ck_ai_usage_reservation_cost"),
    )
    op.create_index("ix_ai_usage_reservation_hospital_status", "ai_usage_reservations", ["hospital_id", "status"])

    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), sa.ForeignKey("ai_usage_reservations.id"), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("operating_mode", sa.String(24), nullable=False),
        sa.Column("provider_id", sa.String(120), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("cost_micros", sa.BigInteger()),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("latency_ms", sa.BigInteger(), nullable=False),
        sa.Column("usage_is_estimated", sa.Boolean(), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("reservation_id", name="uq_ai_usage_event_reservation"),
        sa.CheckConstraint("input_tokens >= 0 AND output_tokens >= 0", name="ck_ai_usage_event_tokens"),
        sa.CheckConstraint("cost_micros IS NULL OR cost_micros >= 0", name="ck_ai_usage_event_cost"),
        sa.CheckConstraint("latency_ms >= 0", name="ck_ai_usage_event_latency"),
        sa.CheckConstraint("outcome IN ('success', 'withheld', 'failed')", name="ck_ai_usage_event_outcome"),
    )
    op.create_index("ix_ai_usage_event_hospital_created", "ai_usage_events", ["hospital_id", "created_at"])
    op.create_index("ix_ai_usage_event_hospital_capability", "ai_usage_events", ["hospital_id", "capability", "created_at"])

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY hospital_tenant_isolation ON {table} "
            "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
            "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
        )

    op.execute("""
        CREATE FUNCTION prevent_ai_usage_event_mutation()
        RETURNS trigger AS $fn$
        BEGIN
            RAISE EXCEPTION 'AI usage events are append-only';
        END;
        $fn$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER ai_usage_events_append_only
        BEFORE UPDATE OR DELETE ON ai_usage_events
        FOR EACH ROW EXECUTE FUNCTION prevent_ai_usage_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ai_usage_events_append_only ON ai_usage_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_ai_usage_event_mutation()")
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS hospital_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_ai_usage_event_hospital_capability", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_event_hospital_created", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
    op.drop_index("ix_ai_usage_reservation_hospital_status", table_name="ai_usage_reservations")
    op.drop_table("ai_usage_reservations")
    op.drop_index("ix_ai_usage_counter_hospital", table_name="ai_usage_counters")
    op.drop_table("ai_usage_counters")
    op.drop_index("ix_ai_usage_policy_hospital_status", table_name="ai_usage_policies")
    op.drop_table("ai_usage_policies")
