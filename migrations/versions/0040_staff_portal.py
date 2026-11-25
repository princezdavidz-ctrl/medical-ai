"""Create clinical staff profiles, patient care-team assignments and staff work queues."""
from alembic import op
import sqlalchemy as sa

revision = "0040_staff_portal"
down_revision = "0039_patient_portal"
branch_labels = None
depends_on = None

TABLES = (
    "clinical_staff_profiles",
    "patient_care_team_assignments",
    "staff_work_queue_tasks",
    "staff_portal_events",
)


def upgrade() -> None:
    op.create_table(
        "clinical_staff_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("employee_profile_id", sa.Uuid(), nullable=False),
        sa.Column("clinical_role", sa.String(32), nullable=False),
        sa.Column("specialty", sa.String(160)),
        sa.Column("professional_title", sa.String(160), nullable=False),
        sa.Column("registration_number", sa.String(120), nullable=False),
        sa.Column("licensing_body", sa.String(160), nullable=False),
        sa.Column("license_expires_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("evidence_reference", sa.String(100)),
        sa.Column("rejection_reason", sa.String(1000)),
        sa.Column("suspension_reason", sa.String(1000)),
        sa.Column("submitted_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "employee_profile_id"], ["employee_profiles.hospital_id", "employee_profiles.id"], name="fk_clinical_staff_employee"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_clinical_staff_profile_hospital_id"),
        sa.UniqueConstraint("hospital_id", "user_id", name="uq_clinical_staff_profile_user"),
        sa.UniqueConstraint("hospital_id", "registration_number", name="uq_clinical_staff_registration_number"),
        sa.CheckConstraint("clinical_role IN ('physician', 'nurse', 'midwife', 'pharmacist', 'clinical_officer', 'dentist', 'therapist', 'radiographer', 'laboratory_scientist', 'other')", name="ck_clinical_staff_role"),
        sa.CheckConstraint("status IN ('pending', 'verified', 'rejected', 'suspended')", name="ck_clinical_staff_status"),
        sa.CheckConstraint("(status IN ('verified', 'suspended') AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL AND evidence_reference IS NOT NULL) OR (status IN ('pending', 'rejected') AND verified_by_user_id IS NULL AND verified_at IS NULL)", name="ck_clinical_staff_verification"),
        sa.CheckConstraint("status != 'rejected' OR rejection_reason IS NOT NULL", name="ck_clinical_staff_rejection_reason"),
        sa.CheckConstraint("status != 'suspended' OR suspension_reason IS NOT NULL", name="ck_clinical_staff_suspension_reason"),
        sa.CheckConstraint("evidence_reference IS NULL OR evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_clinical_staff_evidence_reference"),
    )
    op.create_index("ix_clinical_staff_status_role", "clinical_staff_profiles", ["hospital_id", "status", "clinical_role"])
    op.create_table(
        "patient_care_team_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("staff_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("department_id", sa.Uuid()),
        sa.Column("care_role", sa.String(32), nullable=False),
        sa.Column("access_scope", sa.JSON(), nullable=False, server_default=sa.text("""'["profile","encounters"]'::json""")),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ended_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("end_reason", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_care_team_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_care_team_department"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_care_team_assignment_hospital_id"),
        sa.CheckConstraint("care_role IN ('attending_physician', 'consultant', 'primary_nurse', 'midwife', 'pharmacist', 'case_manager', 'allied_health', 'other')", name="ck_care_team_role"),
        sa.CheckConstraint("status IN ('active', 'ended', 'revoked')", name="ck_care_team_status"),
        sa.CheckConstraint("json_typeof(access_scope) = 'array'", name="ck_care_team_access_scope_array"),
        sa.CheckConstraint("assigned_by_user_id != staff_user_id", name="ck_care_team_no_self_assignment"),
        sa.CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ck_care_team_time_range"),
        sa.CheckConstraint("(status = 'active' AND ended_by_user_id IS NULL AND ended_at IS NULL AND end_reason IS NULL) OR (status IN ('ended', 'revoked') AND ended_by_user_id IS NOT NULL AND ended_at IS NOT NULL AND end_reason IS NOT NULL)", name="ck_care_team_end_state"),
    )
    op.create_index("uq_care_team_active_member", "patient_care_team_assignments", ["hospital_id", "patient_id", "staff_user_id", "care_role"], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_index("ix_care_team_staff_status", "patient_care_team_assignments", ["hospital_id", "staff_user_id", "status"])
    op.create_index("ix_care_team_patient_status", "patient_care_team_assignments", ["hospital_id", "patient_id", "status"])
    op.create_table(
        "staff_work_queue_tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("assigned_to_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid()),
        sa.Column("encounter_id", sa.Uuid()),
        sa.Column("department_id", sa.Uuid()),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completion_note", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_staff_task_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_staff_task_encounter_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_staff_task_department"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_staff_task_hospital_id"),
        sa.CheckConstraint("task_type IN ('review_lab_result', 'sign_note', 'medication_review', 'discharge_planning', 'follow_up', 'referral', 'care_coordination', 'other')", name="ck_staff_task_type"),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_staff_task_priority"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'completed', 'cancelled')", name="ck_staff_task_status"),
        sa.CheckConstraint("encounter_id IS NULL OR patient_id IS NOT NULL", name="ck_staff_task_encounter_patient_required"),
        sa.CheckConstraint("(status = 'completed' AND completed_by_user_id IS NOT NULL AND completed_at IS NOT NULL) OR (status != 'completed' AND completed_by_user_id IS NULL AND completed_at IS NULL)", name="ck_staff_task_completion_state"),
    )
    op.create_index("ix_staff_task_assignee_queue", "staff_work_queue_tasks", ["hospital_id", "assigned_to_user_id", "status", "priority", "due_at"])
    op.create_index("ix_staff_task_patient", "staff_work_queue_tasks", ["hospital_id", "patient_id", "status"])
    op.create_table(
        "staff_portal_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resource_type", sa.String(60), nullable=False),
        sa.Column("resource_id", sa.Uuid()),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "id", name="uq_staff_portal_event_hospital_id"),
        sa.CheckConstraint("event_type IN ('clinical_profile_submitted', 'clinical_profile_verified', 'clinical_profile_rejected', 'clinical_profile_suspended', 'care_team_assigned', 'care_team_ended', 'task_created', 'task_status_changed', 'patient_overview_viewed')", name="ck_staff_portal_event_type"),
    )
    op.create_index("ix_staff_portal_event_history", "staff_portal_events", ["hospital_id", "created_at"])
    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))
    op.execute("""
        CREATE FUNCTION prevent_staff_portal_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'staff portal events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_staff_portal_events_immutable BEFORE UPDATE OR DELETE ON staff_portal_events FOR EACH ROW EXECUTE FUNCTION prevent_staff_portal_event_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_staff_portal_events_immutable ON staff_portal_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_staff_portal_event_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
