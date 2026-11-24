"""Create inpatient wards, beds, admissions and bed assignments."""

from alembic import op
import sqlalchemy as sa

revision = "0019_inpatient_ward"
down_revision = "0018_nursing_workflows"
branch_labels = None
depends_on = None

TABLES = ("wards", "hospital_beds", "inpatient_admissions", "bed_assignments")


def upgrade() -> None:
    op.create_table(
        "wards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("ward_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_ward_department"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_ward_hospital_id_id"),
        sa.UniqueConstraint("hospital_id", "code", name="uq_ward_hospital_code"),
        sa.CheckConstraint("ward_type IN ('general', 'medical', 'surgical', 'maternity', 'pediatric', 'icu', 'other')", name="ck_ward_type"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_ward_status"),
    )

    op.create_table(
        "hospital_beds",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=False),
        sa.Column("bed_number", sa.String(40), nullable=False),
        sa.Column("bed_type", sa.String(24), nullable=False, server_default="standard"),
        sa.Column("status", sa.String(24), nullable=False, server_default="available"),
        sa.Column("isolation_capable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.String(500)),
        sa.ForeignKeyConstraint(["hospital_id", "ward_id"], ["wards.hospital_id", "wards.id"], name="fk_hospital_bed_ward"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_hospital_bed_hospital_id_id"),
        sa.UniqueConstraint("hospital_id", "ward_id", "bed_number", name="uq_hospital_bed_number"),
        sa.CheckConstraint("bed_type IN ('standard', 'isolation', 'high_dependency', 'critical_care', 'maternity', 'pediatric', 'other')", name="ck_hospital_bed_type"),
        sa.CheckConstraint("status IN ('available', 'occupied', 'cleaning', 'maintenance', 'blocked')", name="ck_hospital_bed_status"),
    )
    op.create_index("ix_hospital_beds_ward_status", "hospital_beds", ["hospital_id", "ward_id", "status"])

    op.create_table(
        "inpatient_admissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("source_encounter_id", sa.Uuid()),
        sa.Column("ward_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("accepted_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("discharged_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("admission_reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="requested"),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("admitted_at", sa.DateTime(timezone=True)),
        sa.Column("discharged_at", sa.DateTime(timezone=True)),
        sa.Column("discharge_summary", sa.Text()),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_inpatient_admission_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_inpatient_admission_encounter_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "source_encounter_id"], ["encounters.hospital_id", "encounters.id"], name="fk_inpatient_admission_source_encounter"),
        sa.ForeignKeyConstraint(["hospital_id", "ward_id"], ["wards.hospital_id", "wards.id"], name="fk_inpatient_admission_ward"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_inpatient_admission_hospital_id_id"),
        sa.CheckConstraint("status IN ('requested', 'accepted', 'admitted', 'discharged', 'cancelled')", name="ck_inpatient_admission_status"),
        sa.CheckConstraint("length(trim(admission_reason)) >= 3", name="ck_inpatient_admission_reason"),
    )
    op.create_index(
        "uq_inpatient_active_patient",
        "inpatient_admissions",
        ["hospital_id", "patient_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('requested', 'accepted', 'admitted')"),
    )
    op.create_index("ix_inpatient_admission_ward_status", "inpatient_admissions", ["hospital_id", "ward_id", "status"])

    op.create_table(
        "bed_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("admission_id", sa.Uuid(), nullable=False),
        sa.Column("bed_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("released_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["hospital_id", "admission_id"], ["inpatient_admissions.hospital_id", "inpatient_admissions.id"], name="fk_bed_assignment_admission"),
        sa.ForeignKeyConstraint(["hospital_id", "bed_id"], ["hospital_beds.hospital_id", "hospital_beds.id"], name="fk_bed_assignment_bed"),
        sa.CheckConstraint("status IN ('active', 'released')", name="ck_bed_assignment_status"),
        sa.CheckConstraint("status != 'released' OR released_at IS NOT NULL", name="ck_bed_assignment_release_timestamp"),
    )
    op.create_index(
        "uq_bed_assignment_active_bed", "bed_assignments",
        ["hospital_id", "bed_id"], unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_bed_assignment_active_admission", "bed_assignments",
        ["hospital_id", "admission_id"], unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY hospital_tenant_isolation ON {table} "
            "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
            "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS hospital_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("uq_bed_assignment_active_admission", table_name="bed_assignments")
    op.drop_index("uq_bed_assignment_active_bed", table_name="bed_assignments")
    op.drop_table("bed_assignments")
    op.drop_index("ix_inpatient_admission_ward_status", table_name="inpatient_admissions")
    op.drop_index("uq_inpatient_active_patient", table_name="inpatient_admissions")
    op.drop_table("inpatient_admissions")
    op.drop_index("ix_hospital_beds_ward_status", table_name="hospital_beds")
    op.drop_table("hospital_beds")
    op.drop_table("wards")
