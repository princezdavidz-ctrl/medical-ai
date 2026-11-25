"""Create hospital staff scheduling, shift swaps and manual attendance."""
from alembic import op
import sqlalchemy as sa

revision = "0041_staff_scheduling"
down_revision = "0040_staff_portal"
branch_labels = None
depends_on = None

TABLES = (
    "staff_shift_templates",
    "staff_shift_assignments",
    "staff_shift_swap_requests",
    "staff_shift_attendance",
    "staff_schedule_events",
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_employee_profile_hospital_employee_user",
        "employee_profiles",
        ["hospital_id", "id", "user_id"],
    )
    op.create_table(
        "staff_shift_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Uuid()),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_shift_template_department"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_shift_template_hospital_id"),
        sa.UniqueConstraint("hospital_id", "code", name="uq_shift_template_code"),
        sa.CheckConstraint("category IN ('day', 'evening', 'night', 'on_call', 'other')", name="ck_shift_template_category"),
        sa.CheckConstraint("start_time != end_time", name="ck_shift_template_time_range"),
        sa.CheckConstraint("break_minutes BETWEEN 0 AND 240", name="ck_shift_template_break_minutes"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_shift_template_status"),
    )
    op.create_index("ix_shift_template_department", "staff_shift_templates", ["hospital_id", "department_id", "status"])
    op.create_table(
        "staff_shift_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("employee_profile_id", sa.Uuid(), nullable=False),
        sa.Column("staff_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("department_id", sa.Uuid()),
        sa.Column("shift_template_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="scheduled"),
        sa.Column("assigned_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "employee_profile_id", "staff_user_id"], ["employee_profiles.hospital_id", "employee_profiles.id", "employee_profiles.user_id"], name="fk_staff_shift_employee_user"),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_staff_shift_department"),
        sa.ForeignKeyConstraint(["hospital_id", "shift_template_id"], ["staff_shift_templates.hospital_id", "staff_shift_templates.id"], name="fk_staff_shift_template"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_staff_shift_hospital_id"),
        sa.UniqueConstraint("hospital_id", "id", "staff_user_id", name="uq_staff_shift_hospital_user"),
        sa.CheckConstraint("status IN ('scheduled', 'confirmed', 'completed', 'cancelled')", name="ck_staff_shift_status"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_staff_shift_time_range"),
        sa.CheckConstraint("ends_at <= starts_at + interval '24 hours'", name="ck_staff_shift_max_duration"),
    )
    op.create_index("ix_staff_shift_staff_time", "staff_shift_assignments", ["hospital_id", "staff_user_id", "starts_at", "ends_at"])
    op.create_index("ix_staff_shift_department_time", "staff_shift_assignments", ["hospital_id", "department_id", "starts_at"])
    op.create_index("ix_staff_shift_template_time", "staff_shift_assignments", ["hospital_id", "shift_template_id", "starts_at"])
    op.create_table(
        "staff_shift_swap_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("shift_assignment_id", sa.Uuid(), nullable=False),
        sa.Column("requester_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_target"),
        sa.Column("responded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "shift_assignment_id"], ["staff_shift_assignments.hospital_id", "staff_shift_assignments.id"], name="fk_shift_swap_assignment"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_shift_swap_hospital_id"),
        sa.CheckConstraint("status IN ('pending_target', 'accepted', 'declined', 'approved', 'rejected', 'cancelled')", name="ck_shift_swap_status"),
        sa.CheckConstraint("requester_user_id != target_user_id", name="ck_shift_swap_not_self"),
        sa.CheckConstraint("(status = 'pending_target' AND responded_by_user_id IS NULL AND responded_at IS NULL AND decided_by_user_id IS NULL AND decided_at IS NULL) OR (status IN ('accepted', 'declined') AND responded_by_user_id = target_user_id AND responded_at IS NOT NULL AND decided_by_user_id IS NULL AND decided_at IS NULL) OR (status IN ('approved', 'rejected') AND responded_by_user_id = target_user_id AND responded_at IS NOT NULL AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL) OR status = 'cancelled'", name="ck_shift_swap_decision_state"),
    )
    op.create_index("ix_shift_swap_target_queue", "staff_shift_swap_requests", ["hospital_id", "target_user_id", "status", "created_at"])
    op.create_index("ix_shift_swap_shift", "staff_shift_swap_requests", ["hospital_id", "shift_assignment_id", "status"])
    op.create_table(
        "staff_shift_attendance",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("shift_assignment_id", sa.Uuid(), nullable=False),
        sa.Column("staff_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_out_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(24), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("note", sa.String(1000)),
        sa.Column("decided_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "shift_assignment_id", "staff_user_id"], ["staff_shift_assignments.hospital_id", "staff_shift_assignments.id", "staff_shift_assignments.staff_user_id"], name="fk_shift_attendance_assignment_staff"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_shift_attendance_hospital_id"),
        sa.UniqueConstraint("hospital_id", "shift_assignment_id", name="uq_shift_attendance_per_shift"),
        sa.CheckConstraint("status IN ('open', 'submitted', 'approved', 'rejected')", name="ck_shift_attendance_status"),
        sa.CheckConstraint("check_out_at IS NULL OR check_out_at > check_in_at", name="ck_shift_attendance_time_range"),
        sa.CheckConstraint("(status = 'open' AND check_out_at IS NULL AND decided_by_user_id IS NULL AND decided_at IS NULL) OR (status = 'submitted' AND check_out_at IS NOT NULL AND decided_by_user_id IS NULL AND decided_at IS NULL) OR (status IN ('approved', 'rejected') AND check_out_at IS NOT NULL AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL)", name="ck_shift_attendance_decision_state"),
        sa.CheckConstraint("source = 'manual'", name="ck_shift_attendance_manual_source"),
    )
    op.create_index("ix_shift_attendance_review", "staff_shift_attendance", ["hospital_id", "status", "check_in_at"])
    op.create_table(
        "staff_schedule_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resource_type", sa.String(60), nullable=False),
        sa.Column("resource_id", sa.Uuid()),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "id", name="uq_staff_schedule_event_hospital_id"),
        sa.CheckConstraint("event_type IN ('shift_template_created', 'shift_template_updated', 'shift_assigned', 'shift_updated', 'shift_cancelled', 'swap_requested', 'swap_accepted', 'swap_approved', 'swap_rejected', 'attendance_checked_in', 'attendance_checked_out', 'attendance_approved', 'attendance_rejected')", name="ck_staff_schedule_event_type"),
    )
    op.create_index("ix_staff_schedule_event_history", "staff_schedule_events", ["hospital_id", "created_at"])
    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))
    op.execute("""
        CREATE FUNCTION prevent_staff_schedule_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'staff schedule events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_staff_schedule_events_immutable BEFORE UPDATE OR DELETE ON staff_schedule_events FOR EACH ROW EXECUTE FUNCTION prevent_staff_schedule_event_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_staff_schedule_events_immutable ON staff_schedule_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_staff_schedule_event_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
    op.drop_constraint("uq_employee_profile_hospital_employee_user", "employee_profiles", type_="unique")
