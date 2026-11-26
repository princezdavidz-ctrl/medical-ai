"""Add tenant-isolated communication and notification workflows."""
from alembic import op
import sqlalchemy as sa

revision = "0044_notifications"
down_revision = "0043_telemedicine"
branch_labels = None
depends_on = None

TABLES = (
    "notification_preferences",
    "notification_templates",
    "notification_intents",
    "notification_delivery_attempts",
    "notification_events",
)


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("locale", sa.String(12), nullable=False, server_default="en"),
        sa.Column("timezone_name", sa.String(64), nullable=False, server_default="Africa/Nairobi"),
        sa.Column("quiet_start", sa.String(5)),
        sa.Column("quiet_end", sa.String(5)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_notification_preference_membership"),
        sa.UniqueConstraint("hospital_id", "user_id", name="uq_notification_preference_hospital_user"),
        sa.CheckConstraint("locale ~ '^[a-z]{2}(-[A-Z]{2})?$'", name="ck_notification_preference_locale"),
        sa.CheckConstraint("timezone_name <> ''", name="ck_notification_preference_timezone"),
        sa.CheckConstraint("quiet_start IS NULL OR quiet_start ~ '^[0-2][0-9]:[0-5][0-9]$'", name="ck_notification_quiet_start"),
        sa.CheckConstraint("quiet_end IS NULL OR quiet_end ~ '^[0-2][0-9]:[0-5][0-9]$'", name="ck_notification_quiet_end"),
        sa.CheckConstraint("(quiet_start IS NULL) = (quiet_end IS NULL)", name="ck_notification_quiet_pair"),
    )
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("template_code", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("content_classification", sa.String(20), nullable=False, server_default="operational"),
        sa.Column("title_template", sa.String(160), nullable=False),
        sa.Column("body_template", sa.String(2000), nullable=False),
        sa.Column("allowed_placeholders", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "template_code", "version", name="uq_notification_template_version"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_notification_template_hospital_id"),
        sa.CheckConstraint("channel IN ('in_app', 'email', 'sms', 'push')", name="ck_notification_template_channel"),
        sa.CheckConstraint("status IN ('draft', 'published', 'retired')", name="ck_notification_template_status"),
        sa.CheckConstraint("content_classification IN ('operational', 'administrative', 'sensitive')", name="ck_notification_template_classification"),
        sa.CheckConstraint("version >= 1", name="ck_notification_template_version"),
        sa.CheckConstraint("length(trim(template_code)) BETWEEN 2 AND 80", name="ck_notification_template_code"),
        sa.CheckConstraint("length(trim(title_template)) BETWEEN 1 AND 160", name="ck_notification_template_title"),
        sa.CheckConstraint("length(trim(body_template)) BETWEEN 1 AND 2000", name="ck_notification_template_body"),
    )
    op.create_index("ix_notification_template_lookup", "notification_templates", ["hospital_id", "template_code", "status"])
    op.create_table(
        "notification_intents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid()),
        sa.Column("consent_id", sa.Uuid()),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("purpose", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("rendered_title", sa.String(160), nullable=False),
        sa.Column("rendered_body", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "template_id"], ["notification_templates.hospital_id", "notification_templates.id"], name="fk_notification_intent_template"),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_notification_intent_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_notification_intent_consent"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_notification_intent_hospital_id"),
        sa.UniqueConstraint("hospital_id", "idempotency_key", name="uq_notification_intent_idempotency"),
        sa.CheckConstraint("status IN ('queued', 'processing', 'retry_scheduled', 'delivered', 'failed', 'cancelled')", name="ck_notification_intent_status"),
        sa.CheckConstraint("channel IN ('in_app', 'email', 'sms', 'push')", name="ck_notification_intent_channel"),
        sa.CheckConstraint("attempt_count >= 0 AND attempt_count <= max_attempts AND max_attempts BETWEEN 1 AND 8", name="ck_notification_intent_attempts"),
        sa.CheckConstraint("(patient_id IS NULL AND consent_id IS NULL) OR (patient_id IS NOT NULL AND consent_id IS NOT NULL)", name="ck_notification_intent_patient_consent_pair"),
        sa.CheckConstraint("length(trim(idempotency_key)) BETWEEN 8 AND 128", name="ck_notification_intent_idempotency"),
    )
    op.create_index("ix_notification_dispatch_queue", "notification_intents", ["hospital_id", "status", "next_attempt_at", "created_at"])
    op.create_index("ix_notification_recipient_history", "notification_intents", ["hospital_id", "recipient_user_id", "created_at"])
    op.create_table(
        "notification_delivery_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("intent_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(80), nullable=False, server_default="phase3_stub"),
        sa.Column("provider_reference", sa.String(160)),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "intent_id"], ["notification_intents.hospital_id", "notification_intents.id"], name="fk_notification_attempt_intent"),
        sa.CheckConstraint("outcome IN ('accepted', 'retryable_failure', 'terminal_failure')", name="ck_notification_attempt_outcome"),
        sa.CheckConstraint("attempt_number BETWEEN 1 AND 8", name="ck_notification_attempt_number"),
        sa.UniqueConstraint("hospital_id", "intent_id", "attempt_number", name="uq_notification_attempt_number"),
    )
    op.create_index("ix_notification_attempt_history", "notification_delivery_attempts", ["hospital_id", "intent_id", "created_at"])
    op.create_table(
        "notification_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("intent_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "intent_id"], ["notification_intents.hospital_id", "notification_intents.id"], name="fk_notification_event_intent"),
        sa.CheckConstraint("event_type IN ('enqueued', 'dispatch_started', 'delivery_accepted', 'retry_scheduled', 'delivery_failed', 'cancelled')", name="ck_notification_event_type"),
    )
    op.create_index("ix_notification_event_history", "notification_events", ["hospital_id", "intent_id", "created_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))

    op.execute("""
        CREATE FUNCTION prevent_notification_history_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'notification attempts and events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_notification_attempts_immutable BEFORE UPDATE OR DELETE ON notification_delivery_attempts FOR EACH ROW EXECUTE FUNCTION prevent_notification_history_mutation()")
    op.execute("CREATE TRIGGER trg_notification_events_immutable BEFORE UPDATE OR DELETE ON notification_events FOR EACH ROW EXECUTE FUNCTION prevent_notification_history_mutation()")
    op.execute("""
        CREATE FUNCTION prevent_published_notification_template_mutation() RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'published' THEN
                RAISE EXCEPTION 'published notification templates are immutable; create a new version';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_notification_template_versioned BEFORE UPDATE OR DELETE ON notification_templates FOR EACH ROW EXECUTE FUNCTION prevent_published_notification_template_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_notification_template_versioned ON notification_templates")
    op.execute("DROP FUNCTION IF EXISTS prevent_published_notification_template_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_notification_events_immutable ON notification_events")
    op.execute("DROP TRIGGER IF EXISTS trg_notification_attempts_immutable ON notification_delivery_attempts")
    op.execute("DROP FUNCTION IF EXISTS prevent_notification_history_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
