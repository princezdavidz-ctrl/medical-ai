"""Create pediatric and child-health encounter workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0026_pediatrics"
down_revision = "0025_maternity_surgery_link"
branch_labels = None
depends_on = None

TABLES = (
    "pediatric_care_records",
    "pediatric_growth_observations",
    "pediatric_developmental_screenings",
    "pediatric_immunization_history",
    "pediatric_clinical_notes",
)


def upgrade() -> None:
    op.create_table(
        "pediatric_care_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_pediatric_care_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_pediatric_care_encounter_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_pediatric_care_department",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_pediatric_care_hospital_id"),
        sa.UniqueConstraint("hospital_id", "encounter_id", name="uq_pediatric_care_encounter"),
        sa.CheckConstraint("status IN ('active', 'closed')", name="ck_pediatric_care_status"),
        sa.CheckConstraint(
            "(status = 'active' AND closed_at IS NULL) OR "
            "(status = 'closed' AND closed_at IS NOT NULL)",
            name="ck_pediatric_care_closure_state",
        ),
    )
    op.create_index(
        "ix_pediatric_care_patient_created",
        "pediatric_care_records",
        ["hospital_id", "patient_id", "created_at"],
    )

    op.create_table(
        "pediatric_growth_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("care_record_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("weight_kg", sa.Numeric(7, 2)),
        sa.Column("height_cm", sa.Numeric(6, 2)),
        sa.Column("head_circumference_cm", sa.Numeric(5, 2)),
        sa.Column("mid_upper_arm_cm", sa.Numeric(5, 2)),
        sa.Column("temperature_c", sa.Numeric(4, 1)),
        sa.Column("source", sa.String(16), nullable=False, server_default="measured"),
        sa.Column("notes", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "care_record_id"],
            ["pediatric_care_records.hospital_id", "pediatric_care_records.id"],
            name="fk_pediatric_growth_care_record",
        ),
        sa.CheckConstraint("weight_kg IS NULL OR weight_kg BETWEEN 0.2 AND 300", name="ck_pediatric_growth_weight"),
        sa.CheckConstraint("height_cm IS NULL OR height_cm BETWEEN 20 AND 250", name="ck_pediatric_growth_height"),
        sa.CheckConstraint("head_circumference_cm IS NULL OR head_circumference_cm BETWEEN 10 AND 100", name="ck_pediatric_growth_head"),
        sa.CheckConstraint("mid_upper_arm_cm IS NULL OR mid_upper_arm_cm BETWEEN 5 AND 60", name="ck_pediatric_growth_muac"),
        sa.CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_pediatric_growth_temperature"),
        sa.CheckConstraint("source IN ('measured', 'reported')", name="ck_pediatric_growth_source"),
        sa.CheckConstraint(
            "weight_kg IS NOT NULL OR height_cm IS NOT NULL OR "
            "head_circumference_cm IS NOT NULL OR mid_upper_arm_cm IS NOT NULL OR "
            "temperature_c IS NOT NULL",
            name="ck_pediatric_growth_has_measurement",
        ),
    )
    op.create_index(
        "ix_pediatric_growth_record_time",
        "pediatric_growth_observations",
        ["hospital_id", "care_record_id", "observed_at"],
    )

    op.create_table(
        "pediatric_developmental_screenings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("care_record_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("instrument_name", sa.String(160), nullable=False),
        sa.Column("instrument_version", sa.String(80)),
        sa.Column("domain", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("referral_recommended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()),
        sa.Column("screened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "care_record_id"],
            ["pediatric_care_records.hospital_id", "pediatric_care_records.id"],
            name="fk_pediatric_screening_care_record",
        ),
        sa.CheckConstraint(
            "domain IN ('gross_motor', 'fine_motor', 'language', 'cognitive', 'social_emotional', 'adaptive', 'general')",
            name="ck_pediatric_screening_domain",
        ),
        sa.CheckConstraint(
            "outcome IN ('age_appropriate', 'monitor', 'refer', 'not_assessed', 'unable_to_assess')",
            name="ck_pediatric_screening_outcome",
        ),
        sa.CheckConstraint(
            "outcome != 'refer' OR referral_recommended = true",
            name="ck_pediatric_screening_referral_consistency",
        ),
    )
    op.create_index(
        "ix_pediatric_screening_record_date",
        "pediatric_developmental_screenings",
        ["hospital_id", "care_record_id", "screened_at"],
    )

    op.create_table(
        "pediatric_immunization_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("care_record_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vaccine_label", sa.String(160), nullable=False),
        sa.Column("dose_label", sa.String(80)),
        sa.Column("record_status", sa.String(24), nullable=False),
        sa.Column("source", sa.String(24), nullable=False, server_default="facility_record"),
        sa.Column("administered_at", sa.DateTime(timezone=True)),
        sa.Column("batch_reference", sa.String(120)),
        sa.Column("notes", sa.Text()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "care_record_id"],
            ["pediatric_care_records.hospital_id", "pediatric_care_records.id"],
            name="fk_pediatric_immunization_care_record",
        ),
        sa.CheckConstraint(
            "record_status IN ('administered', 'reported', 'deferred', 'declined', 'unknown')",
            name="ck_pediatric_immunization_status",
        ),
        sa.CheckConstraint(
            "source IN ('facility_record', 'caregiver_report', 'external_record')",
            name="ck_pediatric_immunization_source",
        ),
        sa.CheckConstraint(
            "record_status != 'administered' OR administered_at IS NOT NULL",
            name="ck_pediatric_immunization_administered_at",
        ),
        sa.CheckConstraint(
            "source != 'caregiver_report' OR record_status != 'administered'",
            name="ck_pediatric_immunization_caregiver_provenance",
        ),
    )
    op.create_index(
        "ix_pediatric_immunization_record_date",
        "pediatric_immunization_history",
        ["hospital_id", "care_record_id", "administered_at"],
    )

    op.create_table(
        "pediatric_clinical_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("care_record_id", sa.Uuid(), nullable=False),
        sa.Column("authored_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_type", sa.String(24), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "care_record_id"],
            ["pediatric_care_records.hospital_id", "pediatric_care_records.id"],
            name="fk_pediatric_note_care_record",
        ),
        sa.CheckConstraint(
            "note_type IN ('assessment', 'progress', 'handover', 'discharge', 'other')",
            name="ck_pediatric_note_type",
        ),
        sa.CheckConstraint("length(trim(note_text)) >= 3", name="ck_pediatric_note_text"),
    )
    op.create_index(
        "ix_pediatric_note_record_time",
        "pediatric_clinical_notes",
        ["hospital_id", "care_record_id", "signed_at"],
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
    op.drop_index("ix_pediatric_note_record_time", table_name="pediatric_clinical_notes")
    op.drop_table("pediatric_clinical_notes")
    op.drop_index("ix_pediatric_immunization_record_date", table_name="pediatric_immunization_history")
    op.drop_table("pediatric_immunization_history")
    op.drop_index("ix_pediatric_screening_record_date", table_name="pediatric_developmental_screenings")
    op.drop_table("pediatric_developmental_screenings")
    op.drop_index("ix_pediatric_growth_record_time", table_name="pediatric_growth_observations")
    op.drop_table("pediatric_growth_observations")
    op.drop_index("ix_pediatric_care_patient_created", table_name="pediatric_care_records")
    op.drop_table("pediatric_care_records")
