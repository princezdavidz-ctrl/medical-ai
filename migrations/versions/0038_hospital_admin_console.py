"""Create hospital administration profile, operating settings and department governance."""
from alembic import op
import sqlalchemy as sa

revision = "0038_hospital_admin_console"
down_revision = "0037_mortuary_pathology"
branch_labels = None
depends_on = None

TABLES = (
    "hospital_admin_profiles",
    "hospital_operational_settings",
    "hospital_operating_hours",
    "hospital_admin_events",
)


def upgrade() -> None:
    op.add_column("departments", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("departments", sa.Column("contact_email", sa.String(320), nullable=True))
    op.add_column("departments", sa.Column("contact_phone", sa.String(40), nullable=True))
    op.add_column("departments", sa.Column("manager_user_id", sa.Uuid(), nullable=True))
    op.add_column("departments", sa.Column("parent_department_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_department_manager_user", "departments", "users", ["manager_user_id"], ["id"])
    op.create_foreign_key(
        "fk_department_parent_tenant", "departments", "departments",
        ["hospital_id", "parent_department_id"], ["hospital_id", "id"],
    )
    op.create_check_constraint(
        "ck_department_not_self_parent", "departments",
        "parent_department_id IS NULL OR parent_department_id != id",
    )
    op.create_index("ix_department_parent", "departments", ["hospital_id", "parent_department_id"])

    op.create_table(
        "hospital_admin_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("legal_name", sa.String(240), nullable=False),
        sa.Column("display_name", sa.String(240), nullable=False),
        sa.Column("facility_type", sa.String(32), nullable=False, server_default="general"),
        sa.Column("license_number", sa.String(120)),
        sa.Column("address_line1", sa.String(240), nullable=False),
        sa.Column("address_line2", sa.String(240)),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("county", sa.String(120)),
        sa.Column("postal_code", sa.String(24)),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="KE"),
        sa.Column("primary_phone", sa.String(40), nullable=False),
        sa.Column("emergency_phone", sa.String(40)),
        sa.Column("administrative_email", sa.String(320), nullable=False),
        sa.Column("website_url", sa.String(500)),
        sa.Column("timezone", sa.String(80), nullable=False, server_default="Africa/Nairobi"),
        sa.Column("locale", sa.String(16), nullable=False, server_default="en-KE"),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("brand_primary_color", sa.String(7)),
        sa.Column("brand_secondary_color", sa.String(7)),
        sa.Column("logo_reference", sa.String(160)),
        sa.Column("updated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", name="uq_hospital_admin_profile_hospital"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_hospital_admin_profile_hospital_id"),
        sa.CheckConstraint("length(country_code) = 2 AND country_code = upper(country_code)", name="ck_hospital_profile_country"),
        sa.CheckConstraint("length(currency_code) = 3 AND currency_code = upper(currency_code)", name="ck_hospital_profile_currency"),
        sa.CheckConstraint("facility_type IN ('general', 'specialist', 'teaching', 'referral', 'clinic', 'other')", name="ck_hospital_profile_facility_type"),
        sa.CheckConstraint("brand_primary_color IS NULL OR (length(brand_primary_color) = 7 AND brand_primary_color ~ '^#[0-9A-Fa-f]+$')", name="ck_hospital_profile_primary_color"),
        sa.CheckConstraint("brand_secondary_color IS NULL OR (length(brand_secondary_color) = 7 AND brand_secondary_color ~ '^#[0-9A-Fa-f]+$')", name="ck_hospital_profile_secondary_color"),
    )
    op.create_table(
        "hospital_operational_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("appointment_booking_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("patient_self_registration_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("public_directory_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_appointment_duration_minutes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("appointment_booking_advance_days", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("updated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", name="uq_hospital_operational_settings_hospital"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_hospital_operational_settings_hospital_id"),
        sa.CheckConstraint("default_appointment_duration_minutes BETWEEN 5 AND 240", name="ck_hospital_settings_appointment_duration"),
        sa.CheckConstraint("appointment_booking_advance_days BETWEEN 0 AND 365", name="ck_hospital_settings_advance_days"),
    )
    op.create_table(
        "hospital_operating_hours",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("opens_at", sa.Time()),
        sa.Column("closes_at", sa.Time()),
        sa.Column("updated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "day_of_week", name="uq_hospital_operating_hours_day"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_hospital_operating_hours_hospital_id"),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_hospital_operating_day"),
        sa.CheckConstraint("(is_closed = true AND opens_at IS NULL AND closes_at IS NULL) OR (is_closed = false AND opens_at IS NOT NULL AND closes_at IS NOT NULL AND opens_at < closes_at)", name="ck_hospital_operating_time"),
    )
    op.create_index("ix_hospital_operating_hours_day", "hospital_operating_hours", ["hospital_id", "day_of_week"])
    op.create_table(
        "hospital_admin_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resource_type", sa.String(60), nullable=False),
        sa.Column("resource_id", sa.Uuid()),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "id", name="uq_hospital_admin_event_hospital_id"),
        sa.CheckConstraint("event_type IN ('profile_created', 'profile_updated', 'settings_updated', 'operating_hours_updated', 'department_created', 'department_updated', 'department_deactivated')", name="ck_hospital_admin_event_type"),
    )
    op.create_index("ix_hospital_admin_event_history", "hospital_admin_events", ["hospital_id", "created_at"])
    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))
    op.execute("""
        CREATE FUNCTION prevent_hospital_admin_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'hospital administration events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_hospital_admin_events_immutable BEFORE UPDATE OR DELETE ON hospital_admin_events FOR EACH ROW EXECUTE FUNCTION prevent_hospital_admin_event_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_hospital_admin_events_immutable ON hospital_admin_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_hospital_admin_event_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
    op.drop_index("ix_department_parent", table_name="departments")
    op.drop_constraint("ck_department_not_self_parent", "departments", type_="check")
    op.drop_constraint("fk_department_parent_tenant", "departments", type_="foreignkey")
    op.drop_constraint("fk_department_manager_user", "departments", type_="foreignkey")
    op.drop_column("departments", "parent_department_id")
    op.drop_column("departments", "manager_user_id")
    op.drop_column("departments", "contact_phone")
    op.drop_column("departments", "contact_email")
    op.drop_column("departments", "description")
