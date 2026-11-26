"""Create quality and patient safety workflows."""
from alembic import op
import sqlalchemy as sa

revision = "0047_quality_patient_safety"
down_revision = "0046_notification_read_state"
branch_labels = None
depends_on = None

TABLES = ("safety_incidents", "safety_incident_events", "safety_investigations", "safety_capa_actions")


def upgrade() -> None:
    op.create_table(
        "safety_incidents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Uuid()),
        sa.Column("patient_id", sa.Uuid()),
        sa.Column("encounter_id", sa.Uuid()),
        sa.Column("reporter_user_id", sa.Uuid(), nullable=False),
        sa.Column("reporter_confidential", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="unclassified"),
        sa.Column("harm_level", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(24), nullable=False, server_default="reported"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("immediate_actions", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_safety_incident_department"),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_safety_incident_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_safety_incident_encounter"),
        sa.ForeignKeyConstraint(["hospital_id", "reporter_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_incident_reporter_membership"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_safety_incident_hospital_id"),
        sa.CheckConstraint("category IN ('medication', 'patient_fall', 'diagnostic', 'procedure', 'infection', 'equipment', 'transfusion', 'documentation', 'communication', 'security', 'other')", name="ck_safety_incident_category"),
        sa.CheckConstraint("severity IN ('low', 'moderate', 'high', 'critical', 'unclassified')", name="ck_safety_incident_severity"),
        sa.CheckConstraint("harm_level IN ('none', 'mild', 'moderate', 'severe', 'death', 'unknown')", name="ck_safety_incident_harm"),
        sa.CheckConstraint("status IN ('reported', 'triaged', 'investigating', 'capa_open', 'pending_review', 'closed', 'reopened')", name="ck_safety_incident_status"),
        sa.CheckConstraint("length(trim(summary)) BETWEEN 10 AND 4000", name="ck_safety_incident_summary"),
        sa.CheckConstraint("(patient_id IS NULL AND encounter_id IS NULL) OR patient_id IS NOT NULL", name="ck_safety_incident_patient_encounter_pair"),
    )
    op.create_index("ix_safety_incident_department_status", "safety_incidents", ["hospital_id", "department_id", "status", "reported_at"])
    op.create_index("ix_safety_incident_severity_time", "safety_incidents", ["hospital_id", "severity", "reported_at"])

    op.create_table(
        "safety_incident_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "incident_id"], ["safety_incidents.hospital_id", "safety_incidents.id"], name="fk_safety_incident_event_incident"),
        sa.CheckConstraint("event_type IN ('reported', 'triaged', 'assigned', 'investigation_started', 'investigation_completed', 'capa_created', 'status_changed', 'reopened', 'closed')", name="ck_safety_incident_event_type"),
    )
    op.create_index("ix_safety_incident_event_history", "safety_incident_events", ["hospital_id", "incident_id", "created_at"])

    op.create_table(
        "safety_investigations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="assigned"),
        sa.Column("findings", sa.Text()),
        sa.Column("contributing_factors", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "incident_id"], ["safety_incidents.hospital_id", "safety_incidents.id"], name="fk_safety_investigation_incident"),
        sa.ForeignKeyConstraint(["hospital_id", "assigned_to_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_investigation_assignee"),
        sa.ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_investigation_reviewer"),
        sa.UniqueConstraint("hospital_id", "incident_id", name="uq_safety_investigation_incident"),
        sa.CheckConstraint("status IN ('assigned', 'in_progress', 'pending_review', 'approved', 'rejected')", name="ck_safety_investigation_status"),
        sa.CheckConstraint("reviewed_at IS NULL OR reviewed_by_user_id IS NOT NULL", name="ck_safety_investigation_review_state"),
    )
    op.create_index("ix_safety_investigation_assignee", "safety_investigations", ["hospital_id", "assigned_to_user_id", "status"])

    op.create_table(
        "safety_capa_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("action_description", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("evidence_reference", sa.String(80)),
        sa.Column("effectiveness_review", sa.Text()),
        sa.Column("effectiveness_reviewer_user_id", sa.Uuid()),
        sa.Column("effectiveness_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "incident_id"], ["safety_incidents.hospital_id", "safety_incidents.id"], name="fk_safety_capa_incident"),
        sa.ForeignKeyConstraint(["hospital_id", "owner_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_capa_owner"),
        sa.ForeignKeyConstraint(["hospital_id", "effectiveness_reviewer_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_capa_reviewer"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'pending_effectiveness_review', 'completed', 'cancelled')", name="ck_safety_capa_status"),
        sa.CheckConstraint("evidence_reference IS NULL OR evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_safety_capa_evidence_reference"),
        sa.CheckConstraint("(status = 'completed' AND effectiveness_reviewer_user_id IS NOT NULL AND effectiveness_reviewed_at IS NOT NULL) OR (status != 'completed' AND effectiveness_reviewer_user_id IS NULL AND effectiveness_reviewed_at IS NULL)", name="ck_safety_capa_completion_review"),
    )
    op.create_index("ix_safety_capa_owner_due", "safety_capa_actions", ["hospital_id", "owner_user_id", "status", "due_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))

    op.execute("""
        CREATE FUNCTION prevent_safety_incident_event_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'safety incident events are append-only';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_safety_incident_events_immutable BEFORE UPDATE OR DELETE ON safety_incident_events FOR EACH ROW EXECUTE FUNCTION prevent_safety_incident_event_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_safety_incident_events_immutable ON safety_incident_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_safety_incident_event_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
