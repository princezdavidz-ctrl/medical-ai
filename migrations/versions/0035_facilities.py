"""Create tenant-isolated facilities locations and maintenance workflows."""
from alembic import op
import sqlalchemy as sa

revision = "0035_facilities"
down_revision = "0034_inventory"
branch_labels = None
depends_on = None

TABLES = ("facility_locations", "maintenance_work_orders", "maintenance_events")


def upgrade() -> None:
    op.create_table(
        "facility_locations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("parent_location_id", sa.Uuid()),
        sa.Column("location_code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("location_type", sa.String(32), nullable=False),
        sa.Column("building", sa.String(120)),
        sa.Column("floor", sa.String(40)),
        sa.Column("room_number", sa.String(40)),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "parent_location_id"], ["facility_locations.hospital_id", "facility_locations.id"], name="fk_facility_location_parent"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_facility_location_hospital_id"),
        sa.UniqueConstraint("hospital_id", "location_code", name="uq_facility_location_code"),
        sa.CheckConstraint("location_type IN ('campus', 'building', 'floor', 'wing', 'department', 'room', 'utility_area', 'external_area')", name="ck_facility_location_type"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'closed')", name="ck_facility_location_status"),
        sa.CheckConstraint("parent_location_id IS NULL OR parent_location_id != id", name="ck_facility_location_not_self_parent"),
    )
    op.create_index("ix_facility_location_parent", "facility_locations", ["hospital_id", "parent_location_id"])
    op.create_table(
        "maintenance_work_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("work_order_number", sa.String(80), nullable=False),
        sa.Column("facility_location_id", sa.Uuid(), nullable=False),
        sa.Column("asset_record_id", sa.Uuid()),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("priority", sa.String(24), nullable=False, server_default="normal"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="requested"),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_to_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("assigned_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completion_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "facility_location_id"], ["facility_locations.hospital_id", "facility_locations.id"], name="fk_maintenance_order_location"),
        sa.ForeignKeyConstraint(["hospital_id", "asset_record_id"], ["asset_records.hospital_id", "asset_records.id"], name="fk_maintenance_order_asset"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_maintenance_order_hospital_id"),
        sa.UniqueConstraint("hospital_id", "work_order_number", name="uq_maintenance_order_number"),
        sa.CheckConstraint("category IN ('electrical', 'plumbing', 'hvac', 'building', 'medical_equipment', 'safety', 'other')", name="ck_maintenance_order_category"),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_maintenance_order_priority"),
        sa.CheckConstraint("status IN ('requested', 'approved', 'assigned', 'in_progress', 'completed', 'rejected', 'cancelled')", name="ck_maintenance_order_status"),
        sa.CheckConstraint("(status IN ('requested', 'rejected', 'cancelled') AND approved_by_user_id IS NULL AND approved_at IS NULL) OR (status IN ('approved', 'assigned', 'in_progress', 'completed') AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)", name="ck_maintenance_order_approval_state"),
        sa.CheckConstraint("(status IN ('assigned', 'in_progress', 'completed') AND assigned_to_user_id IS NOT NULL AND assigned_by_user_id IS NOT NULL AND assigned_at IS NOT NULL) OR (status IN ('requested', 'approved', 'rejected', 'cancelled') AND assigned_to_user_id IS NULL AND assigned_by_user_id IS NULL AND assigned_at IS NULL)", name="ck_maintenance_order_assignment_state"),
        sa.CheckConstraint("(status = 'completed' AND completed_by_user_id IS NOT NULL AND completed_at IS NOT NULL AND completion_note IS NOT NULL) OR (status != 'completed' AND completed_by_user_id IS NULL AND completed_at IS NULL AND completion_note IS NULL)", name="ck_maintenance_order_completion_state"),
    )
    op.create_index("ix_maintenance_order_queue", "maintenance_work_orders", ["hospital_id", "status", "priority", "created_at"])
    op.create_index("ix_maintenance_order_asset", "maintenance_work_orders", ["hospital_id", "asset_record_id", "created_at"])
    op.create_table(
        "maintenance_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("work_order_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "work_order_id"], ["maintenance_work_orders.hospital_id", "maintenance_work_orders.id"], name="fk_maintenance_event_order"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_maintenance_event_hospital_id"),
    )
    op.create_index("ix_maintenance_event_order_time", "maintenance_events", ["hospital_id", "work_order_id", "created_at"])
    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))
    op.execute("""
        CREATE FUNCTION prevent_maintenance_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'maintenance events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_maintenance_events_immutable
        BEFORE UPDATE OR DELETE ON maintenance_events
        FOR EACH ROW EXECUTE FUNCTION prevent_maintenance_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_maintenance_events_immutable ON maintenance_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_maintenance_event_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
