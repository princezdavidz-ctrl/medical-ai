"""Add hospital-scoped patient care assignments for patient-context authorization."""
from alembic import op
import sqlalchemy as sa

revision = "0010_patient_care_assignments"
down_revision = "0009_durable_offline_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_care_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("staff_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("department_id", sa.Uuid(), sa.ForeignKey("departments.id")),
        sa.Column("encounter_id", sa.Uuid(), sa.ForeignKey("encounters.id")),
        sa.Column("assignment_reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'revoked', 'expired')", name="ck_patient_care_assignment_status"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_patient_care_assignment_validity"),
    )
    op.create_index(
        "ix_patient_care_assignment_staff_patient",
        "patient_care_assignments",
        ["hospital_id", "staff_user_id", "patient_id", "status"],
    )
    op.create_index(
        "ix_patient_care_assignment_encounter",
        "patient_care_assignments",
        ["hospital_id", "encounter_id", "status"],
    )
    op.execute("ALTER TABLE patient_care_assignments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE patient_care_assignments FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY hospital_tenant_isolation ON patient_care_assignments
        USING (
            hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        )
        WITH CHECK (
            hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS hospital_tenant_isolation ON patient_care_assignments")
    op.execute("ALTER TABLE patient_care_assignments NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE patient_care_assignments DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_patient_care_assignment_encounter", table_name="patient_care_assignments")
    op.drop_index("ix_patient_care_assignment_staff_patient", table_name="patient_care_assignments")
    op.drop_table("patient_care_assignments")
