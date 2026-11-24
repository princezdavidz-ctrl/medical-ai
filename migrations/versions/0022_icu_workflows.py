"""Create ICU stay, observation and clinical documentation tables."""

from alembic import op
import sqlalchemy as sa

revision = "0022_icu_workflows"
down_revision = "0021_inpatient_composite_keys"
branch_labels = None
depends_on = None

TABLES = ("icu_stays", "icu_observations", "icu_care_events", "icu_progress_notes")


def upgrade() -> None:
    op.create_table(
        "icu_stays",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("admission_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("bed_assignment_id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("started_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("admission_reason", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("stepdown_requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("stepdown_requested_at", sa.DateTime(timezone=True)),
        sa.Column("closed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["hospital_id", "admission_id", "patient_id"],
            ["inpatient_admissions.hospital_id", "inpatient_admissions.id", "inpatient_admissions.patient_id"],
            name="fk_icu_stay_admission_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "bed_assignment_id", "admission_id"],
            ["bed_assignments.hospital_id", "bed_assignments.id", "bed_assignments.admission_id"],
            name="fk_icu_stay_bed_assignment_admission",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_icu_stay_encounter_patient",
        ),
        sa.ForeignKeyConstraint(["hospital_id", "ward_id"], ["wards.hospital_id", "wards.id"], name="fk_icu_stay_ward"),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_icu_stay_department"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_icu_stay_hospital_id_id"),
        sa.CheckConstraint("status IN ('active', 'stepdown_requested', 'closed')", name="ck_icu_stay_status"),
        sa.CheckConstraint("length(trim(admission_reason)) >= 3", name="ck_icu_stay_admission_reason"),
    )
    op.create_index(
        "uq_icu_active_admission", "icu_stays",
        ["hospital_id", "admission_id"], unique=True,
        postgresql_where=sa.text("status IN ('active', 'stepdown_requested')"),
    )
    op.create_index("ix_icu_stay_department_status", "icu_stays", ["hospital_id", "department_id", "status"])

    op.create_table(
        "icu_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("stay_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("heart_rate", sa.Numeric(6, 2)),
        sa.Column("respiratory_rate", sa.Numeric(6, 2)),
        sa.Column("temperature_c", sa.Numeric(4, 1)),
        sa.Column("systolic_bp", sa.Numeric(6, 2)),
        sa.Column("diastolic_bp", sa.Numeric(6, 2)),
        sa.Column("spo2_percent", sa.Numeric(5, 2)),
        sa.Column("pain_score", sa.Integer()),
        sa.Column("gcs_eye", sa.Integer()),
        sa.Column("gcs_verbal", sa.Integer()),
        sa.Column("gcs_motor", sa.Integer()),
        sa.Column("oxygen_support", sa.String(120)),
        sa.Column("ventilation_mode", sa.String(120)),
        sa.Column("urine_output_ml", sa.Numeric(10, 2)),
        sa.Column("fluid_intake_ml", sa.Numeric(10, 2)),
        sa.Column("fluid_output_ml", sa.Numeric(10, 2)),
        sa.Column("notes", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "stay_id"], ["icu_stays.hospital_id", "icu_stays.id"], name="fk_icu_observation_stay"),
        sa.CheckConstraint("heart_rate IS NULL OR heart_rate BETWEEN 1 AND 300", name="ck_icu_obs_hr"),
        sa.CheckConstraint("respiratory_rate IS NULL OR respiratory_rate BETWEEN 1 AND 100", name="ck_icu_obs_rr"),
        sa.CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_icu_obs_temp"),
        sa.CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_icu_obs_systolic"),
        sa.CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_icu_obs_diastolic"),
        sa.CheckConstraint("systolic_bp IS NULL OR diastolic_bp IS NULL OR systolic_bp > diastolic_bp", name="ck_icu_obs_bp_order"),
        sa.CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_icu_obs_spo2"),
        sa.CheckConstraint("pain_score IS NULL OR pain_score BETWEEN 0 AND 10", name="ck_icu_obs_pain"),
        sa.CheckConstraint("gcs_eye IS NULL OR gcs_eye BETWEEN 1 AND 4", name="ck_icu_obs_gcs_eye"),
        sa.CheckConstraint("gcs_verbal IS NULL OR gcs_verbal BETWEEN 1 AND 5", name="ck_icu_obs_gcs_verbal"),
        sa.CheckConstraint("gcs_motor IS NULL OR gcs_motor BETWEEN 1 AND 6", name="ck_icu_obs_gcs_motor"),
        sa.CheckConstraint("urine_output_ml IS NULL OR urine_output_ml >= 0", name="ck_icu_obs_urine_output"),
        sa.CheckConstraint("fluid_intake_ml IS NULL OR fluid_intake_ml >= 0", name="ck_icu_obs_fluid_intake"),
        sa.CheckConstraint("fluid_output_ml IS NULL OR fluid_output_ml >= 0", name="ck_icu_obs_fluid_output"),
    )
    op.create_index("ix_icu_observation_stay", "icu_observations", ["hospital_id", "stay_id", "observed_at"])

    op.create_table(
        "icu_care_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("stay_id", sa.Uuid(), nullable=False),
        sa.Column("performed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "stay_id"], ["icu_stays.hospital_id", "icu_stays.id"], name="fk_icu_care_event_stay"),
        sa.CheckConstraint("event_type IN ('assessment', 'intervention', 'procedure', 'airway_support', 'ventilation_change', 'handover', 'other')", name="ck_icu_care_event_type"),
        sa.CheckConstraint("length(trim(description)) >= 3", name="ck_icu_care_event_description"),
    )
    op.create_index("ix_icu_care_event_stay", "icu_care_events", ["hospital_id", "stay_id", "performed_at"])

    op.create_table(
        "icu_progress_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("stay_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_type", sa.String(24), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "stay_id"], ["icu_stays.hospital_id", "icu_stays.id"], name="fk_icu_progress_note_stay"),
        sa.CheckConstraint("note_type IN ('daily_review', 'progress', 'handover', 'incident', 'other')", name="ck_icu_progress_note_type"),
        sa.CheckConstraint("length(trim(note_text)) >= 3", name="ck_icu_progress_note_text"),
    )
    op.create_index("ix_icu_progress_note_stay", "icu_progress_notes", ["hospital_id", "stay_id", "signed_at"])

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
    op.drop_index("ix_icu_progress_note_stay", table_name="icu_progress_notes")
    op.drop_table("icu_progress_notes")
    op.drop_index("ix_icu_care_event_stay", table_name="icu_care_events")
    op.drop_table("icu_care_events")
    op.drop_index("ix_icu_observation_stay", table_name="icu_observations")
    op.drop_table("icu_observations")
    op.drop_index("ix_icu_stay_department_status", table_name="icu_stays")
    op.drop_index("uq_icu_active_admission", table_name="icu_stays")
    op.drop_table("icu_stays")
