"""Create hospital notifications, delivery outbox and secure messaging."""
from alembic import op
import sqlalchemy as sa

revision = "0044_communications"
down_revision = "0043_telemedicine"
branch_labels = None
depends_on = None

TABLES = (
    "notification_preferences",
    "hospital_notifications",
    "notification_deliveries",
    "notification_outbox",
    "communication_threads",
    "communication_messages",
    "communication_message_receipts",
    "communication_events",
)


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("muted_categories", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("quiet_hours_start", sa.Time()),
        sa.Column("quiet_hours_end", sa.Time()),
        sa.Column("timezone_name", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "user_id", name="uq_notification_preference_user"),
        sa.CheckConstraint("json_typeof(muted_categories) = 'array'", name="ck_notification_muted_categories"),
        sa.CheckConstraint("(quiet_hours_start IS NULL AND quiet_hours_end IS NULL) OR (quiet_hours_start IS NOT NULL AND quiet_hours_end IS NOT NULL)", name="ck_notification_quiet_hours_pair"),
    )
    op.create_index("ix_notification_preferences_user", "notification_preferences", ["hospital_id", "user_id"])

    op.create_table(
        "hospital_notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recipient_type", sa.String(12), nullable=False),
        sa.Column("patient_id", sa.Uuid()),
        sa.Column("portal_link_id", sa.Uuid()),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("deep_link", sa.String(500)),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("contains_sensitive_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("read_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_notification_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "portal_link_id", "patient_id", "recipient_user_id"], ["patient_portal_links.hospital_id", "patient_portal_links.id", "patient_portal_links.patient_id", "patient_portal_links.portal_user_id"], name="fk_notification_patient_portal_link"),
        sa.UniqueConstraint("hospital_id", "id", "recipient_user_id", name="uq_notification_hospital_id_recipient"),
        sa.UniqueConstraint("hospital_id", "idempotency_key", name="uq_notification_idempotency"),
        sa.CheckConstraint("recipient_type IN ('patient', 'staff')", name="ck_notification_recipient_type"),
        sa.CheckConstraint("category IN ('appointment', 'clinical_update', 'laboratory', 'radiology', 'medication', 'billing', 'insurance', 'records', 'telemedicine', 'transfer', 'staff_schedule', 'security', 'system', 'message', 'other')", name="ck_notification_category"),
        sa.CheckConstraint("priority IN ('normal', 'high', 'urgent', 'critical')", name="ck_notification_priority"),
        sa.CheckConstraint("status IN ('queued', 'partially_delivered', 'delivered', 'failed', 'cancelled')", name="ck_notification_status"),
        sa.CheckConstraint("json_typeof(channels) = 'array' AND json_array_length(channels) > 0", name="ck_notification_channels"),
        sa.CheckConstraint("NOT contains_sensitive_data OR (json_array_length(channels) = 1 AND channels->>0 = 'in_app')", name="ck_notification_sensitive_in_app_only"),
        sa.CheckConstraint("(recipient_type = 'patient' AND patient_id IS NOT NULL AND portal_link_id IS NOT NULL) OR (recipient_type = 'staff' AND patient_id IS NULL AND portal_link_id IS NULL)", name="ck_notification_patient_recipient_link"),
        sa.CheckConstraint("(read_at IS NULL AND read_by_user_id IS NULL) OR (read_at IS NOT NULL AND read_by_user_id = recipient_user_id)", name="ck_notification_read_state"),
        sa.CheckConstraint("(status = 'cancelled' AND cancelled_at IS NOT NULL AND cancelled_by_user_id IS NOT NULL) OR (status != 'cancelled' AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL)", name="ck_notification_cancel_state"),
    )
    op.create_index("ix_notification_recipient_inbox", "hospital_notifications", ["hospital_id", "recipient_user_id", "status", "created_at"])
    op.create_index("ix_notification_category_queue", "hospital_notifications", ["hospital_id", "category", "created_at"])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(1000)),
        sa.Column("provider_message_id", sa.String(180)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "notification_id", "recipient_user_id"], ["hospital_notifications.hospital_id", "hospital_notifications.id", "hospital_notifications.recipient_user_id"], name="fk_notification_delivery_notification"),
        sa.UniqueConstraint("hospital_id", "notification_id", "channel", name="uq_notification_delivery_channel"),
        sa.CheckConstraint("channel IN ('in_app', 'email', 'sms')", name="ck_notification_delivery_channel"),
        sa.CheckConstraint("status IN ('pending', 'processing', 'sent', 'delivered', 'failed', 'cancelled')", name="ck_notification_delivery_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_notification_delivery_attempts"),
    )
    op.create_index("ix_notification_delivery_queue", "notification_deliveries", ["hospital_id", "status", "next_attempt_at"])

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False, server_default="notification.dispatch_requested"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("locked_by", sa.String(120)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "notification_id", "recipient_user_id"], ["hospital_notifications.hospital_id", "hospital_notifications.id", "hospital_notifications.recipient_user_id"], name="fk_notification_outbox_notification"),
        sa.UniqueConstraint("hospital_id", "idempotency_key", name="uq_notification_outbox_idempotency"),
        sa.CheckConstraint("status IN ('pending', 'processing', 'published', 'failed', 'cancelled')", name="ck_notification_outbox_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_notification_outbox_attempts"),
    )
    op.create_index("ix_notification_outbox_claim", "notification_outbox", ["status", "available_at", "created_at"])

    op.create_table(
        "communication_threads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("portal_link_id", sa.Uuid(), nullable=False),
        sa.Column("patient_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_staff_user_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(180), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="open"),
        sa.Column("opened_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("closed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("close_reason", sa.String(1000)),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_communication_thread_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "portal_link_id", "patient_id", "patient_user_id"], ["patient_portal_links.hospital_id", "patient_portal_links.id", "patient_portal_links.patient_id", "patient_portal_links.portal_user_id"], name="fk_communication_thread_portal_link"),
        sa.ForeignKeyConstraint(["hospital_id", "assigned_staff_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_communication_thread_assigned_staff"),
        sa.UniqueConstraint("hospital_id", "id", "patient_id", "portal_link_id", "patient_user_id", "assigned_staff_user_id", name="uq_communication_thread_participants"),
        sa.CheckConstraint("category IN ('care_question', 'appointment', 'billing', 'records', 'technical_support', 'other')", name="ck_communication_thread_category"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_communication_thread_status"),
        sa.CheckConstraint("length(trim(subject)) >= 2", name="ck_communication_thread_subject"),
        sa.CheckConstraint("(status = 'open' AND closed_by_user_id IS NULL AND closed_at IS NULL AND close_reason IS NULL) OR (status = 'closed' AND closed_by_user_id IS NOT NULL AND closed_at IS NOT NULL AND close_reason IS NOT NULL)", name="ck_communication_thread_close_state"),
    )
    op.create_index("ix_communication_thread_staff", "communication_threads", ["hospital_id", "assigned_staff_user_id", "status", "last_message_at"])
    op.create_index("ix_communication_thread_patient", "communication_threads", ["hospital_id", "patient_user_id", "status", "last_message_at"])

    op.create_table(
        "communication_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("portal_link_id", sa.Uuid(), nullable=False),
        sa.Column("patient_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_staff_user_id", sa.Uuid(), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sender_type", sa.String(12), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "thread_id", "patient_id", "portal_link_id", "patient_user_id", "assigned_staff_user_id"], ["communication_threads.hospital_id", "communication_threads.id", "communication_threads.patient_id", "communication_threads.portal_link_id", "communication_threads.patient_user_id", "communication_threads.assigned_staff_user_id"], name="fk_communication_message_thread"),
        sa.UniqueConstraint("hospital_id", "id", "thread_id", "patient_id", name="uq_communication_message_thread_patient"),
        sa.CheckConstraint("sender_type IN ('patient', 'staff')", name="ck_communication_message_sender_type"),
        sa.CheckConstraint("(sender_type = 'patient' AND sender_user_id = patient_user_id) OR (sender_type = 'staff' AND sender_user_id = assigned_staff_user_id)", name="ck_communication_message_sender_identity"),
        sa.CheckConstraint("length(trim(body)) >= 1 AND length(body) <= 5000", name="ck_communication_message_body"),
    )
    op.create_index("ix_communication_message_thread", "communication_messages", ["hospital_id", "thread_id", "created_at"])

    op.create_table(
        "communication_message_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("reader_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "message_id", "thread_id", "patient_id"], ["communication_messages.hospital_id", "communication_messages.id", "communication_messages.thread_id", "communication_messages.patient_id"], name="fk_communication_receipt_message"),
        sa.UniqueConstraint("hospital_id", "message_id", "reader_user_id", name="uq_communication_message_reader"),
        sa.CheckConstraint("read_at IS NOT NULL", name="ck_communication_receipt_read_at"),
    )
    op.create_index("ix_communication_receipt_thread", "communication_message_receipts", ["hospital_id", "thread_id", "reader_user_id"])

    op.create_table(
        "communication_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "thread_id", "patient_id"], ["communication_threads.hospital_id", "communication_threads.id", "communication_threads.patient_id"], name="fk_communication_event_thread"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_communication_event_hospital_id"),
        sa.CheckConstraint("event_type IN ('thread_opened', 'message_sent', 'message_read', 'thread_closed')", name="ck_communication_event_type"),
    )
    op.create_index("ix_communication_event_thread", "communication_events", ["hospital_id", "thread_id", "created_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))

    op.execute("""
        CREATE FUNCTION prevent_communication_immutable() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'communication messages, receipts and events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_communication_messages_immutable BEFORE UPDATE OR DELETE ON communication_messages FOR EACH ROW EXECUTE FUNCTION prevent_communication_immutable()")
    op.execute("CREATE TRIGGER trg_communication_receipts_immutable BEFORE UPDATE OR DELETE ON communication_message_receipts FOR EACH ROW EXECUTE FUNCTION prevent_communication_immutable()")
    op.execute("CREATE TRIGGER trg_communication_events_immutable BEFORE UPDATE OR DELETE ON communication_events FOR EACH ROW EXECUTE FUNCTION prevent_communication_immutable()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_communication_events_immutable ON communication_events")
    op.execute("DROP TRIGGER IF EXISTS trg_communication_receipts_immutable ON communication_message_receipts")
    op.execute("DROP TRIGGER IF EXISTS trg_communication_messages_immutable ON communication_messages")
    op.execute("DROP FUNCTION IF EXISTS prevent_communication_immutable()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
