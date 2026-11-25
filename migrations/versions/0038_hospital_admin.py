"""Hospital administration settings and tenant-safe role membership constraints."""
from alembic import op
import sqlalchemy as sa

revision = "0038_hospital_admin"
down_revision = "0037_mortuary_pathology"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_role_hospital_id", "roles", ["hospital_id", "id"])
    op.create_foreign_key(
        "fk_membership_role_tenant", "hospital_memberships", "roles",
        ["hospital_id", "role_id"], ["hospital_id", "id"],
    )
    op.create_foreign_key(
        "fk_membership_department_tenant", "hospital_memberships", "departments",
        ["hospital_id", "department_id"], ["hospital_id", "id"],
    )
    op.create_table(
        "hospital_admin_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("contact_email", sa.String(320)),
        sa.Column("contact_phone", sa.String(40)),
        sa.Column("website_url", sa.String(500)),
        sa.Column("timezone_name", sa.String(80), nullable=False, server_default="Africa/Nairobi"),
        sa.Column("locale", sa.String(20), nullable=False, server_default="en-KE"),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="KE"),
        sa.Column("updated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", name="uq_hospital_admin_settings_hospital"),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="ck_hospital_admin_currency"),
        sa.CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="ck_hospital_admin_country"),
    )
    op.execute("ALTER TABLE hospital_admin_settings ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY hospital_admin_settings_hospital_isolation
        ON hospital_admin_settings
        USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)
        WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS hospital_admin_settings_hospital_isolation ON hospital_admin_settings")
    op.execute("ALTER TABLE hospital_admin_settings DISABLE ROW LEVEL SECURITY")
    op.drop_table("hospital_admin_settings")
    op.drop_constraint("fk_membership_department_tenant", "hospital_memberships", type_="foreignkey")
    op.drop_constraint("fk_membership_role_tenant", "hospital_memberships", type_="foreignkey")
    op.drop_constraint("uq_role_hospital_id", "roles", type_="unique")
