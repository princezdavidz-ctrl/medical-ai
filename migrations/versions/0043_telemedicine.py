"""Create telemedicine remote-care session workflows."""
from alembic import op
import sqlalchemy as sa

revision = "0043_telemedicine"
down_revision = "0042_patient_records"
branch_labels = None
depends_on = None

TABLES = (
    "telemedicine_sessions",
    "telemedicine_clinical_notes",
    "telemedicine_events",
)


def upgrade() -> None:
    op.create_table(
        "telemedicine_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("provider_employee_profile_id", sa.Uuid(), nullable=False),
        sa.Column("provider_user_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("consent_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid()),
        sa.Column("visit_reason", sa.String(500), nullable=False),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="scheduled"),
        sa.Column("patient_ready_at", sa.DateTime(timezone=True)),
        sa.Column("patient_ready_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("patient_location_reference", sa.String(80)),
        sa.Column("emergency_contact_reference", sa.String(80)),
        sa.Column("safety_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("safety_confirmed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("patient_identity_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("privacy_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("emergency_plan_acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("started_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("ended_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_reason", sa.String(1000)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_telemedicine_session_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "provider_employee_profile_id", "provider_user_id"], ["employee_profiles.hospital_id", "employee_profiles.id", "employee_profiles.user_id"], name="fk_telemedicine_session_provider_employee"),
        sa.ForeignKeyConstraint(["hospital_id", "provider_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_telemedicine_session_provider_membership"),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_telemedicine_session_department"),
        sa.ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_telemedicine_session_consent"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_telemedicine_session_encounter"),
        sa.UniqueConstraint("hospital_id", "id", "patient_id", name="uq_telemedicine_session_hospital_id_patient"),
        sa.CheckConstraint("status IN ('scheduled', 'patient_ready', 'in_progress', 'completed', 'cancelled', 'no_show')", name="ck_telemedicine_session_status"),
        sa.CheckConstraint("scheduled_end > scheduled_start AND scheduled_end <= scheduled_start + interval '2 hours'", name="ck_telemedicine_session_duration"),
        sa.CheckConstraint("length(trim(visit_reason)) >= 3", name="ck_telemedicine_session_reason"),
        sa.CheckConstraint("patient_location_reference IS NULL OR patient_location_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_telemedicine_location_ref"),
        sa.CheckConstraint("emergency_contact_reference IS NULL OR emergency_contact_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_telemedicine_emergency_ref"),
        sa.CheckConstraint("(status IN ('scheduled', 'cancelled', 'no_show') AND (status != 'scheduled' OR (patient_ready_at IS NULL AND patient_ready_by_user_id IS NULL AND patient_location_reference IS NULL AND emergency_contact_reference IS NULL AND safety_confirmed_at IS NULL AND safety_confirmed_by_user_id IS NULL AND patient_identity_confirmed = false AND privacy_confirmed = false AND emergency_plan_acknowledged = false))) OR (status IN ('patient_ready', 'in_progress', 'completed') AND patient_ready_at IS NOT NULL AND patient_ready_by_user_id IS NOT NULL AND patient_location_reference IS NOT NULL AND emergency_contact_reference IS NOT NULL AND safety_confirmed_at IS NOT NULL AND safety_confirmed_by_user_id IS NOT NULL AND patient_identity_confirmed = true AND privacy_confirmed = true AND emergency_plan_acknowledged = true)", name="ck_telemedicine_safety_state"),
        sa.CheckConstraint("(status IN ('scheduled', 'patient_ready', 'cancelled', 'no_show') AND encounter_id IS NULL AND started_at IS NULL AND started_by_user_id IS NULL AND ended_at IS NULL AND ended_by_user_id IS NULL) OR (status = 'in_progress' AND encounter_id IS NOT NULL AND started_at IS NOT NULL AND started_by_user_id IS NOT NULL AND ended_at IS NULL AND ended_by_user_id IS NULL) OR (status = 'completed' AND encounter_id IS NOT NULL AND started_at IS NOT NULL AND started_by_user_id IS NOT NULL AND ended_at IS NOT NULL AND ended_by_user_id IS NOT NULL AND ended_at > started_at)", name="ck_telemedicine_session_time_state"),
        sa.CheckConstraint("(status IN ('cancelled', 'no_show') AND cancelled_by_user_id IS NOT NULL AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL) OR (status NOT IN ('cancelled', 'no_show') AND cancelled_by_user_id IS NULL AND cancelled_at IS NULL AND cancellation_reason IS NULL)", name="ck_telemedicine_session_cancel_state"),
    )
    op.create_index("ix_telemedicine_patient_schedule", "telemedicine_sessions", ["hospital_id", "patient_id", "scheduled_start", "status"])
    op.create_index("ix_telemedicine_provider_schedule", "telemedicine_sessions", ["hospital_id", "provider_user_id", "scheduled_start", "status"])
    op.create_index("ix_telemedicine_department_schedule", "telemedicine_sessions", ["hospital_id", "department_id", "scheduled_start", "status"])

    op.create_table(
        "telemedicine_clinical_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_type", sa.String(24), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "session_id", "patient_id"], ["telemedicine_sessions.hospital_id", "telemedicine_sessions.id", "telemedicine_sessions.patient_id"], name="fk_telemedicine_note_session"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_telemedicine_note_encounter"),
        sa.UniqueConstraint("hospital_id", "id", "patient_id", name="uq_telemedicine_note_hospital_id_patient"),
        sa.CheckConstraint("note_type IN ('consultation', 'assessment', 'plan', 'follow_up', 'safety_plan', 'referral')", name="ck_telemedicine_note_type"),
        sa.CheckConstraint("length(trim(note_text)) >= 10", name="ck_telemedicine_note_text"),
        sa.CheckConstraint("signed_at IS NOT NULL", name="ck_telemedicine_note_signed"),
    )
    op.create_index("ix_telemedicine_note_session", "telemedicine_clinical_notes", ["hospital_id", "session_id", "created_at"])
    op.create_index("ix_telemedicine_note_patient", "telemedicine_clinical_notes", ["hospital_id", "patient_id", "created_at"])

    op.create_table(
        "telemedicine_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(48), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "session_id", "patient_id"], ["telemedicine_sessions.hospital_id", "telemedicine_sessions.id", "telemedicine_sessions.patient_id"], name="fk_telemedicine_event_session"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_telemedicine_event_hospital_id"),
        sa.CheckConstraint("event_type IN ('session_scheduled', 'patient_ready', 'session_started', 'note_signed', 'session_completed', 'session_cancelled', 'session_no_show')", name="ck_telemedicine_event_type"),
    )
    op.create_index("ix_telemedicine_event_history", "telemedicine_events", ["hospital_id", "session_id", "created_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))

    op.execute("""
        CREATE FUNCTION prevent_telemedicine_immutable() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'telemedicine notes and events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_telemedicine_notes_immutable BEFORE UPDATE OR DELETE ON telemedicine_clinical_notes FOR EACH ROW EXECUTE FUNCTION prevent_telemedicine_immutable()")
    op.execute("CREATE TRIGGER trg_telemedicine_events_immutable BEFORE UPDATE OR DELETE ON telemedicine_events FOR EACH ROW EXECUTE FUNCTION prevent_telemedicine_immutable()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_telemedicine_events_immutable ON telemedicine_events")
    op.execute("DROP TRIGGER IF EXISTS trg_telemedicine_notes_immutable ON telemedicine_clinical_notes")
    op.execute("DROP FUNCTION IF EXISTS prevent_telemedicine_immutable()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
