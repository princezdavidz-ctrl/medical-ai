"""Create maternity, labor, delivery, newborn and postpartum workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0024_maternity_newborn"
down_revision = "0023_surgery_theatre"
branch_labels = None
depends_on = None

TABLES = (
    "maternity_episodes",
    "maternity_antenatal_visits",
    "labor_records",
    "labor_observations",
    "maternity_deliveries",
    "maternity_newborns",
    "maternity_postpartum_observations",
    "maternity_newborn_observations",
    "maternity_notes",
)


def upgrade() -> None:
    op.create_table(
        "maternity_episodes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("pregnancy_number", sa.Integer(), nullable=False),
        sa.Column("gravida", sa.Integer(), nullable=False),
        sa.Column("para", sa.Integer(), nullable=False),
        sa.Column("last_menstrual_period", sa.Date()),
        sa.Column("estimated_due_date", sa.Date()),
        sa.Column("pregnancy_status", sa.String(24), nullable=False, server_default="antenatal"),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_reason", sa.Text()),
        sa.Column("pregnancy_end_reason", sa.String(24)),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_maternity_episode_mother"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_maternity_episode_encounter_mother"),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_maternity_episode_department"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_maternity_episode_hospital_id_id"),
        sa.UniqueConstraint("hospital_id", "id", "patient_id", name="uq_maternity_episode_hospital_id_patient"),
        sa.UniqueConstraint("hospital_id", "patient_id", "pregnancy_number", name="uq_maternity_episode_pregnancy_number"),
        sa.CheckConstraint("pregnancy_number >= 1", name="ck_maternity_episode_pregnancy_number"),
        sa.CheckConstraint("gravida >= 1 AND para >= 0 AND para <= gravida", name="ck_maternity_episode_gravida_para"),
        sa.CheckConstraint("pregnancy_status IN ('antenatal', 'in_labor', 'postpartum', 'ended')", name="ck_maternity_episode_pregnancy_status"),
        sa.CheckConstraint("pregnancy_status != 'ended' OR pregnancy_end_reason IS NOT NULL", name="ck_maternity_episode_end_reason"),
        sa.CheckConstraint("pregnancy_end_reason IS NULL OR pregnancy_end_reason IN ('miscarriage', 'ectopic', 'termination', 'other')", name="ck_maternity_episode_end_reason_value"),
        sa.CheckConstraint("status IN ('active', 'closed')", name="ck_maternity_episode_status"),
        sa.CheckConstraint("status != 'closed' OR (closed_at IS NOT NULL AND closed_reason IS NOT NULL)", name="ck_maternity_episode_closed_fields"),
        sa.CheckConstraint("pregnancy_status != 'ended' OR status = 'closed'", name="ck_maternity_episode_ended_closed"),
        sa.CheckConstraint("closed_reason IS NULL OR length(trim(closed_reason)) >= 3", name="ck_maternity_episode_closed_reason"),
    )
    op.create_index(
        "uq_maternity_active_episode_patient", "maternity_episodes",
        ["hospital_id", "patient_id"], unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_maternity_episode_department_status", "maternity_episodes", ["hospital_id", "department_id", "status"])

    op.create_table(
        "maternity_antenatal_visits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("provider_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("gestational_age_weeks", sa.SmallInteger(), nullable=False),
        sa.Column("gestational_age_days", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("systolic_bp", sa.Numeric(6, 2)),
        sa.Column("diastolic_bp", sa.Numeric(6, 2)),
        sa.Column("weight_kg", sa.Numeric(6, 2)),
        sa.Column("fetal_heart_rate", sa.Integer()),
        sa.Column("fundal_height_cm", sa.Numeric(5, 2)),
        sa.Column("fetal_movement_reported", sa.Boolean()),
        sa.Column("notes", sa.Text()),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "episode_id"], ["maternity_episodes.hospital_id", "maternity_episodes.id"], name="fk_maternity_antenatal_visit_episode"),
        sa.CheckConstraint("gestational_age_weeks BETWEEN 0 AND 45", name="ck_antenatal_gestational_weeks"),
        sa.CheckConstraint("gestational_age_days BETWEEN 0 AND 6", name="ck_antenatal_gestational_days"),
        sa.CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_antenatal_systolic"),
        sa.CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_antenatal_diastolic"),
        sa.CheckConstraint("systolic_bp IS NULL OR diastolic_bp IS NULL OR systolic_bp > diastolic_bp", name="ck_antenatal_bp_order"),
        sa.CheckConstraint("weight_kg IS NULL OR weight_kg BETWEEN 0.2 AND 500", name="ck_antenatal_weight"),
        sa.CheckConstraint("fetal_heart_rate IS NULL OR fetal_heart_rate BETWEEN 50 AND 240", name="ck_antenatal_fhr"),
        sa.CheckConstraint("fundal_height_cm IS NULL OR fundal_height_cm BETWEEN 0 AND 60", name="ck_antenatal_fundal_height"),
    )
    op.create_index("ix_antenatal_visit_episode_date", "maternity_antenatal_visits", ["hospital_id", "episode_id", "visited_at"])

    op.create_table(
        "labor_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("lead_midwife_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="latent"),
        sa.Column("onset_type", sa.String(24), nullable=False),
        sa.Column("membrane_status", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("presentation", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["hospital_id", "episode_id"], ["maternity_episodes.hospital_id", "maternity_episodes.id"], name="fk_labor_record_episode"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_labor_record_hospital_id_id"),
        sa.UniqueConstraint("hospital_id", "id", "episode_id", name="uq_labor_record_hospital_id_episode"),
        sa.UniqueConstraint("hospital_id", "episode_id", name="uq_labor_record_episode"),
        sa.CheckConstraint("status IN ('latent', 'active', 'second_stage', 'delivered', 'ended')", name="ck_labor_record_status"),
        sa.CheckConstraint("(status IN ('delivered', 'ended') AND ended_at IS NOT NULL) OR (status NOT IN ('delivered', 'ended') AND ended_at IS NULL)", name="ck_labor_record_end_state"),
        sa.CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_labor_record_end_time"),
        sa.CheckConstraint("onset_type IN ('spontaneous', 'induced', 'augmented', 'other')", name="ck_labor_record_onset"),
        sa.CheckConstraint("membrane_status IN ('intact', 'ruptured', 'unknown')", name="ck_labor_record_membranes"),
        sa.CheckConstraint("presentation IN ('cephalic', 'breech', 'transverse', 'other', 'unknown')", name="ck_labor_record_presentation"),
    )

    op.create_table(
        "labor_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("labor_record_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("labor_stage", sa.String(24), nullable=False),
        sa.Column("cervical_dilation_cm", sa.Numeric(4, 1)),
        sa.Column("fetal_heart_rate", sa.Integer()),
        sa.Column("contractions_per_10_min", sa.Integer()),
        sa.Column("contraction_duration_seconds", sa.Integer()),
        sa.Column("maternal_heart_rate", sa.Integer()),
        sa.Column("systolic_bp", sa.Numeric(6, 2)),
        sa.Column("diastolic_bp", sa.Numeric(6, 2)),
        sa.Column("temperature_c", sa.Numeric(4, 1)),
        sa.Column("spo2_percent", sa.Numeric(5, 2)),
        sa.Column("membrane_status", sa.String(24)),
        sa.Column("amniotic_fluid_description", sa.String(500)),
        sa.Column("notes", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "labor_record_id"], ["labor_records.hospital_id", "labor_records.id"], name="fk_labor_observation_record"),
        sa.CheckConstraint("labor_stage IN ('latent', 'active', 'second_stage')", name="ck_labor_observation_stage"),
        sa.CheckConstraint("membrane_status IS NULL OR membrane_status IN ('intact', 'ruptured', 'unknown')", name="ck_labor_observation_membranes"),
        sa.CheckConstraint("cervical_dilation_cm IS NULL OR cervical_dilation_cm BETWEEN 0 AND 10", name="ck_labor_cervical_dilation"),
        sa.CheckConstraint("fetal_heart_rate IS NULL OR fetal_heart_rate BETWEEN 50 AND 240", name="ck_labor_fhr"),
        sa.CheckConstraint("contractions_per_10_min IS NULL OR contractions_per_10_min BETWEEN 0 AND 10", name="ck_labor_contractions"),
        sa.CheckConstraint("contraction_duration_seconds IS NULL OR contraction_duration_seconds BETWEEN 0 AND 300", name="ck_labor_contraction_duration"),
        sa.CheckConstraint("maternal_heart_rate IS NULL OR maternal_heart_rate BETWEEN 1 AND 300", name="ck_labor_maternal_hr"),
        sa.CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_labor_systolic"),
        sa.CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_labor_diastolic"),
        sa.CheckConstraint("systolic_bp IS NULL OR diastolic_bp IS NULL OR systolic_bp > diastolic_bp", name="ck_labor_bp_order"),
        sa.CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_labor_temperature"),
        sa.CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_labor_spo2"),
    )
    op.create_index("ix_labor_observation_record_time", "labor_observations", ["hospital_id", "labor_record_id", "observed_at"])

    op.create_table(
        "maternity_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("labor_record_id", sa.Uuid()),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("mother_patient_id", sa.Uuid(), nullable=False),
        sa.Column("delivered_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("delivery_mode", sa.String(32), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("placenta_delivered_at", sa.DateTime(timezone=True)),
        sa.Column("estimated_blood_loss_ml", sa.Numeric(10, 2)),
        sa.Column("complications", sa.Text()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "labor_record_id", "episode_id"], ["labor_records.hospital_id", "labor_records.id", "labor_records.episode_id"], name="fk_maternity_delivery_labor_episode"),
        sa.ForeignKeyConstraint(["hospital_id", "episode_id", "mother_patient_id"], ["maternity_episodes.hospital_id", "maternity_episodes.id", "maternity_episodes.patient_id"], name="fk_maternity_delivery_episode_mother"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_maternity_delivery_hospital_id_id"),
        sa.UniqueConstraint("hospital_id", "id", "mother_patient_id", name="uq_maternity_delivery_hospital_id_mother"),
        sa.UniqueConstraint("hospital_id", "labor_record_id", name="uq_maternity_delivery_labor"),
        sa.UniqueConstraint("hospital_id", "episode_id", name="uq_maternity_delivery_episode"),
        sa.CheckConstraint("delivery_mode IN ('spontaneous_vaginal', 'assisted_vaginal', 'cesarean', 'breech', 'other')", name="ck_maternity_delivery_mode"),
        sa.CheckConstraint("estimated_blood_loss_ml IS NULL OR estimated_blood_loss_ml BETWEEN 0 AND 50000", name="ck_maternity_delivery_blood_loss"),
        sa.CheckConstraint("placenta_delivered_at IS NULL OR placenta_delivered_at >= delivered_at", name="ck_maternity_delivery_placenta_time"),
    )

    op.create_table(
        "maternity_newborns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("delivery_id", sa.Uuid(), nullable=False),
        sa.Column("mother_patient_id", sa.Uuid(), nullable=False),
        sa.Column("newborn_patient_id", sa.Uuid()),
        sa.Column("birth_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sex", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("birth_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("birth_weight_g", sa.Numeric(8, 2)),
        sa.Column("length_cm", sa.Numeric(5, 2)),
        sa.Column("head_circumference_cm", sa.Numeric(5, 2)),
        sa.Column("apgar_1_minute", sa.Integer()),
        sa.Column("apgar_5_minute", sa.Integer()),
        sa.Column("apgar_10_minute", sa.Integer()),
        sa.Column("resuscitation_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(["hospital_id", "delivery_id", "mother_patient_id"], ["maternity_deliveries.hospital_id", "maternity_deliveries.id", "maternity_deliveries.mother_patient_id"], name="fk_maternity_newborn_delivery_mother"),
        sa.ForeignKeyConstraint(["hospital_id", "mother_patient_id"], ["patients.hospital_id", "patients.id"], name="fk_maternity_newborn_mother"),
        sa.ForeignKeyConstraint(["hospital_id", "newborn_patient_id"], ["patients.hospital_id", "patients.id"], name="fk_maternity_newborn_patient"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_maternity_newborn_hospital_id_id"),
        sa.UniqueConstraint("hospital_id", "delivery_id", "birth_order", name="uq_maternity_newborn_birth_order"),
        sa.UniqueConstraint("hospital_id", "newborn_patient_id", name="uq_maternity_newborn_patient_link"),
        sa.CheckConstraint("birth_order >= 1", name="ck_maternity_newborn_birth_order"),
        sa.CheckConstraint("sex IN ('female', 'male', 'intersex', 'unknown')", name="ck_maternity_newborn_sex"),
        sa.CheckConstraint("outcome IN ('live_birth', 'stillbirth', 'neonatal_death')", name="ck_maternity_newborn_outcome"),
        sa.CheckConstraint("birth_weight_g IS NULL OR birth_weight_g BETWEEN 100 AND 10000", name="ck_maternity_newborn_weight"),
        sa.CheckConstraint("length_cm IS NULL OR length_cm BETWEEN 10 AND 100", name="ck_maternity_newborn_length"),
        sa.CheckConstraint("head_circumference_cm IS NULL OR head_circumference_cm BETWEEN 10 AND 70", name="ck_maternity_newborn_head"),
        sa.CheckConstraint("apgar_1_minute IS NULL OR apgar_1_minute BETWEEN 0 AND 10", name="ck_maternity_newborn_apgar1"),
        sa.CheckConstraint("apgar_5_minute IS NULL OR apgar_5_minute BETWEEN 0 AND 10", name="ck_maternity_newborn_apgar5"),
        sa.CheckConstraint("apgar_10_minute IS NULL OR apgar_10_minute BETWEEN 0 AND 10", name="ck_maternity_newborn_apgar10"),
        sa.CheckConstraint("outcome != 'stillbirth' OR newborn_patient_id IS NULL", name="ck_maternity_newborn_patient_only_live"),
    )
    op.create_index("ix_maternity_newborn_mother", "maternity_newborns", ["hospital_id", "mother_patient_id", "birth_at"])

    op.create_table(
        "maternity_postpartum_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("maternal_heart_rate", sa.Integer()),
        sa.Column("systolic_bp", sa.Numeric(6, 2)),
        sa.Column("diastolic_bp", sa.Numeric(6, 2)),
        sa.Column("temperature_c", sa.Numeric(4, 1)),
        sa.Column("spo2_percent", sa.Numeric(5, 2)),
        sa.Column("estimated_blood_loss_ml", sa.Numeric(10, 2)),
        sa.Column("uterine_tone", sa.String(24), nullable=False, server_default="not_assessed"),
        sa.Column("lochia", sa.String(24), nullable=False, server_default="not_assessed"),
        sa.Column("breastfeeding_initiated", sa.Boolean()),
        sa.Column("notes", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "episode_id"], ["maternity_episodes.hospital_id", "maternity_episodes.id"], name="fk_maternity_postpartum_episode"),
        sa.CheckConstraint("maternal_heart_rate IS NULL OR maternal_heart_rate BETWEEN 1 AND 300", name="ck_postpartum_hr"),
        sa.CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_postpartum_systolic"),
        sa.CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_postpartum_diastolic"),
        sa.CheckConstraint("systolic_bp IS NULL OR diastolic_bp IS NULL OR systolic_bp > diastolic_bp", name="ck_postpartum_bp_order"),
        sa.CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_postpartum_temperature"),
        sa.CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_postpartum_spo2"),
        sa.CheckConstraint("estimated_blood_loss_ml IS NULL OR estimated_blood_loss_ml BETWEEN 0 AND 50000", name="ck_postpartum_blood_loss"),
        sa.CheckConstraint("uterine_tone IN ('firm', 'boggy', 'not_assessed')", name="ck_postpartum_uterine_tone"),
        sa.CheckConstraint("lochia IN ('normal', 'heavy', 'not_assessed')", name="ck_postpartum_lochia"),
    )
    op.create_index("ix_postpartum_episode_time", "maternity_postpartum_observations", ["hospital_id", "episode_id", "observed_at"])

    op.create_table(
        "maternity_newborn_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("newborn_record_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("temperature_c", sa.Numeric(4, 1)),
        sa.Column("heart_rate", sa.Integer()),
        sa.Column("respiratory_rate", sa.Integer()),
        sa.Column("spo2_percent", sa.Numeric(5, 2)),
        sa.Column("feeding_status", sa.String(24), nullable=False, server_default="not_assessed"),
        sa.Column("urine_output_count", sa.Integer()),
        sa.Column("stool_count", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "newborn_record_id"], ["maternity_newborns.hospital_id", "maternity_newborns.id"], name="fk_maternity_newborn_observation_record"),
        sa.CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_newborn_obs_temp"),
        sa.CheckConstraint("heart_rate IS NULL OR heart_rate BETWEEN 1 AND 300", name="ck_newborn_obs_hr"),
        sa.CheckConstraint("respiratory_rate IS NULL OR respiratory_rate BETWEEN 1 AND 150", name="ck_newborn_obs_rr"),
        sa.CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_newborn_obs_spo2"),
        sa.CheckConstraint("feeding_status IN ('breastfeeding', 'expressed_milk', 'formula', 'not_feeding', 'not_assessed')", name="ck_newborn_obs_feeding"),
        sa.CheckConstraint("urine_output_count IS NULL OR urine_output_count BETWEEN 0 AND 100", name="ck_newborn_obs_urine_count"),
        sa.CheckConstraint("stool_count IS NULL OR stool_count BETWEEN 0 AND 100", name="ck_newborn_obs_stool_count"),
    )
    op.create_index("ix_newborn_observation_record_time", "maternity_newborn_observations", ["hospital_id", "newborn_record_id", "observed_at"])

    op.create_table(
        "maternity_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_type", sa.String(24), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "episode_id"], ["maternity_episodes.hospital_id", "maternity_episodes.id"], name="fk_maternity_note_episode"),
        sa.CheckConstraint("note_type IN ('antenatal', 'labor', 'delivery', 'postpartum', 'handover', 'other')", name="ck_maternity_note_type"),
        sa.CheckConstraint("length(trim(note_text)) >= 3", name="ck_maternity_note_text"),
    )
    op.create_index("ix_maternity_note_episode", "maternity_notes", ["hospital_id", "episode_id", "signed_at"])

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
    op.drop_index("ix_maternity_note_episode", table_name="maternity_notes")
    op.drop_table("maternity_notes")
    op.drop_index("ix_newborn_observation_record_time", table_name="maternity_newborn_observations")
    op.drop_table("maternity_newborn_observations")
    op.drop_index("ix_postpartum_episode_time", table_name="maternity_postpartum_observations")
    op.drop_table("maternity_postpartum_observations")
    op.drop_index("ix_maternity_newborn_mother", table_name="maternity_newborns")
    op.drop_table("maternity_newborns")
    op.drop_table("maternity_deliveries")
    op.drop_index("ix_labor_observation_record_time", table_name="labor_observations")
    op.drop_table("labor_observations")
    op.drop_table("labor_records")
    op.drop_index("ix_antenatal_visit_episode_date", table_name="maternity_antenatal_visits")
    op.drop_table("maternity_antenatal_visits")
    op.drop_index("ix_maternity_episode_department_status", table_name="maternity_episodes")
    op.drop_index("uq_maternity_active_episode_patient", table_name="maternity_episodes")
    op.drop_table("maternity_episodes")
