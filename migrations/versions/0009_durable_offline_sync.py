"""Durable, hospital-scoped offline knowledge and synchronization state."""
from alembic import op
import sqlalchemy as sa

revision = "0009_durable_offline_sync"
down_revision = "0008_ai_evaluation_governance"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "offline_knowledge_installations",
    "offline_sync_cursors",
    "offline_sync_events",
    "offline_sync_conflicts",
    "offline_delivery_outbox",
)


def upgrade() -> None:
    op.create_table(
        "offline_knowledge_installations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("package_id", sa.String(160), nullable=False),
        sa.Column("snapshot_version", sa.String(100), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("signing_key_id", sa.String(160), nullable=False),
        sa.Column("jurisdiction", sa.String(80), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True)),
        sa.Column("encrypted_storage_ref", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "package_id", name="uq_offline_install_hospital_package"),
        sa.CheckConstraint("status IN ('verified', 'installed', 'stale', 'revoked', 'failed')", name="ck_offline_install_status"),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_offline_install_digest"),
    )
    op.create_index("ix_offline_install_hospital_status", "offline_knowledge_installations", ["hospital_id", "status"])

    op.create_table(
        "offline_sync_cursors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("source_node_id", sa.String(160), nullable=False),
        sa.Column("stream_name", sa.String(100), nullable=False),
        sa.Column("last_sequence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_event_id", sa.String(160)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "source_node_id", "stream_name", name="uq_offline_sync_cursor_stream"),
        sa.CheckConstraint("last_sequence >= 0", name="ck_offline_sync_cursor_sequence"),
    )
    op.create_index("ix_offline_sync_cursor_hospital", "offline_sync_cursors", ["hospital_id"])

    op.create_table(
        "offline_sync_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("source_node_id", sa.String(160), nullable=False),
        sa.Column("stream_name", sa.String(100), nullable=False),
        sa.Column("event_id", sa.String(160), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("encrypted_storage_ref", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("hospital_id", "source_node_id", "stream_name", "event_id", name="uq_offline_sync_event_identity"),
        sa.UniqueConstraint("hospital_id", "source_node_id", "stream_name", "sequence_number", name="uq_offline_sync_event_sequence"),
        sa.CheckConstraint("status IN ('queued', 'conflict', 'applied', 'acknowledged', 'rejected')", name="ck_offline_sync_event_status"),
        sa.CheckConstraint("sequence_number > 0", name="ck_offline_sync_event_sequence_positive"),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_offline_sync_event_digest"),
    )
    op.create_index("ix_offline_sync_event_pending", "offline_sync_events", ["hospital_id", "status", "sequence_number"])

    op.create_table(
        "offline_sync_conflicts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("offline_sync_events.id")),
        sa.Column("source_node_id", sa.String(160), nullable=False),
        sa.Column("stream_name", sa.String(100), nullable=False),
        sa.Column("incoming_event_id", sa.String(160), nullable=False),
        sa.Column("incoming_sequence", sa.BigInteger(), nullable=False),
        sa.Column("conflict_code", sa.String(100), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("resolved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('open', 'resolved', 'rejected')", name="ck_offline_sync_conflict_status"),
    )
    op.create_index("ix_offline_sync_conflict_hospital_status", "offline_sync_conflicts", ["hospital_id", "status"])

    op.create_table(
        "offline_delivery_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("destination_node_id", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("encrypted_storage_ref", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(120)),
        sa.Column("partner_ack_reference", sa.String(240)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "destination_node_id", "idempotency_key", name="uq_offline_outbox_idempotency"),
        sa.CheckConstraint("status IN ('queued', 'sending', 'delivered', 'failed', 'cancelled')", name="ck_offline_outbox_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_offline_outbox_attempt_count"),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_offline_outbox_digest"),
    )
    op.create_index("ix_offline_outbox_dispatch", "offline_delivery_outbox", ["hospital_id", "status", "next_attempt_at"])

    # Every row is isolated by the hospital selected in the authenticated request context.
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY hospital_tenant_isolation ON {table} "
            "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
            "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
        )


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS hospital_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_offline_outbox_dispatch", table_name="offline_delivery_outbox")
    op.drop_table("offline_delivery_outbox")
    op.drop_index("ix_offline_sync_conflict_hospital_status", table_name="offline_sync_conflicts")
    op.drop_table("offline_sync_conflicts")
    op.drop_index("ix_offline_sync_event_pending", table_name="offline_sync_events")
    op.drop_table("offline_sync_events")
    op.drop_index("ix_offline_sync_cursor_hospital", table_name="offline_sync_cursors")
    op.drop_table("offline_sync_cursors")
    op.drop_index("ix_offline_install_hospital_status", table_name="offline_knowledge_installations")
    op.drop_table("offline_knowledge_installations")
