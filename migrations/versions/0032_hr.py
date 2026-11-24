"""Create hospital HR staff, credential and leave workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0032_hr"
down_revision = "0031_insurance"
branch_labels = None
depends_on = None

TABLES = ("employee_profiles", "staff_credentials", "staff_leave_requests")


def upgrade() -> None:
    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("department_id", sa.Uuid()),
        sa.Column("employee_number", sa.String(80), nullable=False),
        sa.Column("job_title", sa.String(160), nullable=False),
        sa.Column("employment_type", sa.String(24), nullable=False),
        sa.Column("employment_status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True)),
        sa.Column("manager_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_employee_profile_department"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_employee_profile_hospital_id"),
        sa.UniqueConstraint("hospital_id", "user_id", name="uq_employee_profile_user"),
        sa.UniqueConstraint("hospital_id", "employee_number", name="uq_employee_profile_number"),
        sa.CheckConstraint("employment_status IN ('active', 'on_leave', 'suspended', 'terminated')", name="ck_employee_profile_status"),
        sa.CheckConstraint("employment_type IN ('permanent', 'contract', 'locum', 'intern', 'volunteer', 'other')", name="ck_employee_profile_type"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_employee_profile_dates"),
    )
    op.create_index("ix_employee_profile_department_status", "employee_profiles", ["hospital_id", "department_id", "employment_status"])

    op.create_table(
        "staff_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("employee_profile_id", sa.Uuid(), nullable=False),
        sa.Column("credential_type", sa.String(100), nullable=False),
        sa.Column("credential_number", sa.String(160), nullable=False),
        sa.Column("issuing_body", sa.String(180), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("verification_status", sa.String(24), nullable=False, server_default="reported"),
        sa.Column("evidence_reference", sa.String(160)),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "employee_profile_id"], ["employee_profiles.hospital_id", "employee_profiles.id"], name="fk_staff_credential_employee"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_staff_credential_hospital_id"),
        sa.CheckConstraint("verification_status IN ('reported', 'verified', 'rejected', 'expired')", name="ck_staff_credential_status"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until >= valid_from", name="ck_staff_credential_dates"),
        sa.CheckConstraint("(verification_status = 'verified' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL) OR verification_status != 'verified'", name="ck_staff_credential_verification"),
    )
    op.create_index("ix_staff_credential_employee", "staff_credentials", ["hospital_id", "employee_profile_id", "verification_status"])

    op.create_table(
        "staff_leave_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("employee_profile_id", sa.Uuid(), nullable=False),
        sa.Column("leave_type", sa.String(40), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decided_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "employee_profile_id"], ["employee_profiles.hospital_id", "employee_profiles.id"], name="fk_staff_leave_employee"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_staff_leave_hospital_id"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name="ck_staff_leave_status"),
        sa.CheckConstraint("end_at > start_at", name="ck_staff_leave_dates"),
    )
    op.create_index("ix_staff_leave_queue", "staff_leave_requests", ["hospital_id", "status", "start_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(
            f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" '
            "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
            "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
        ))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
