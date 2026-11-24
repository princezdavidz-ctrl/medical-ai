"""Create nursing assessment, observation, note and care plan workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0018_nursing_workflows"
down_revision = "0017_opd_workflows"
branch_labels = None
depends_on = None

TABLES = (
    "nursing_assessments",
    "nursing_observations",
    "nursing_notes",
    "nursing_care_plans",
    "nursing_care_plan_reviews",
)


def upgrade() -> None:
    op.create_table(
        "nursing_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("assessed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assessment_type", sa.String(24), nullable=False),
        sa.Column("general_condition", sa.String(500)),
        sa.Column("mental_status", sa.String(500)),
        sa.Column("mobility_status", sa.String(500)),
        sa.Column("skin_assessment", sa.Text()),
        sa.Column("pain_score", sa.SmallInteger()),
        sa.Column("fall_risk_level", sa.String(24)),
        sa.Column("pressure_injury_risk_level", sa.String(24)),
        sa.Column("nutrition_concerns", sa.Text()),
        sa.Column("nursing_concerns", sa.Text()),
        sa.Column("assessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_nursing_assessment_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id"], ["encounters.hospital_id", "encounters.id"], name="fk_nursing_assessment_encounter"),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_nursing_assessment_department"),
        sa.CheckConstraint("assessment_type IN ('admission', 'shift', 'focused', 'discharge')", name="ck_nursing_assessment_type"),
        sa.CheckConstraint("pain_score IS NULL OR pain_score BETWEEN 0 AND 10", name="ck_nursing_assessment_pain"),
        sa.CheckConstraint("fall_risk_level IS NULL OR fall_risk_level IN ('low', 'moderate', 'high', 'not_assessed')", name="ck_nursing_assessment_fall_risk"),
        sa.CheckConstraint("pressure_injury_risk_level IS NULL OR pressure_injury_risk_level IN ('low', 'moderate', 'high', 'not_assessed')", name="ck_nursing_assessment_pressure_risk"),
    )
    op.create_index("ix_nursing_assessment_encounter", "nursing_assessments", ["hospital_id", "encounter_id", "assessed_at"])

    op.create_table(
        "nursing_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("heart_rate", sa.Numeric(6, 2)),
        sa.Column("respiratory_rate", sa.Numeric(6, 2)),
        sa.Column("temperature_c", sa.Numeric(4, 1)),
        sa.Column("systolic_bp", sa.Numeric(6, 2)),
        sa.Column("diastolic_bp", sa.Numeric(6, 2)),
        sa.Column("spo2_percent", sa.Numeric(5, 2)),
        sa.Column("pain_score", sa.SmallInteger()),
        sa.Column("consciousness_level", sa.String(16)),
        sa.Column("oxygen_delivery", sa.String(120)),
        sa.Column("intake_ml", sa.Numeric(10, 2)),
        sa.Column("output_ml", sa.Numeric(10, 2)),
        sa.Column("notes", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_nursing_observation_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id"], ["encounters.hospital_id", "encounters.id"], name="fk_nursing_observation_encounter"),
        sa.CheckConstraint("heart_rate IS NULL OR heart_rate BETWEEN 1 AND 300", name="ck_nursing_obs_hr"),
        sa.CheckConstraint("respiratory_rate IS NULL OR respiratory_rate BETWEEN 1 AND 100", name="ck_nursing_obs_rr"),
        sa.CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_nursing_obs_temp"),
        sa.CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_nursing_obs_systolic"),
        sa.CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_nursing_obs_diastolic"),
        sa.CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_nursing_obs_spo2"),
        sa.CheckConstraint("pain_score IS NULL OR pain_score BETWEEN 0 AND 10", name="ck_nursing_obs_pain"),
        sa.CheckConstraint("systolic_bp IS NULL OR diastolic_bp IS NULL OR systolic_bp > diastolic_bp", name="ck_nursing_obs_bp_order"),
        sa.CheckConstraint("intake_ml IS NULL OR intake_ml >= 0", name="ck_nursing_obs_intake"),
        sa.CheckConstraint("output_ml IS NULL OR output_ml >= 0", name="ck_nursing_obs_output"),
    )
    op.create_index("ix_nursing_observation_encounter", "nursing_observations", ["hospital_id", "encounter_id", "observed_at"])

    op.create_table(
        "nursing_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_type", sa.String(24), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_nursing_note_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id"], ["encounters.hospital_id", "encounters.id"], name="fk_nursing_note_encounter"),
        sa.CheckConstraint("note_type IN ('shift_handover', 'progress', 'incident', 'discharge', 'other')", name="ck_nursing_note_type"),
        sa.CheckConstraint("length(trim(note_text)) >= 3", name="ck_nursing_note_text"),
    )
    op.create_index("ix_nursing_note_encounter", "nursing_notes", ["hospital_id", "encounter_id", "signed_at"])

    op.create_table(
        "nursing_care_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nursing_diagnosis", sa.String(1000), nullable=False),
        sa.Column("goals", sa.Text(), nullable=False),
        sa.Column("interventions", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_nursing_care_plan_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id"], ["encounters.hospital_id", "encounters.id"], name="fk_nursing_care_plan_encounter"),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_nursing_care_plan_department"),
        sa.CheckConstraint("status IN ('active', 'completed', 'cancelled')", name="ck_nursing_care_plan_status"),
        sa.CheckConstraint("length(trim(nursing_diagnosis)) >= 3", name="ck_nursing_care_plan_diagnosis"),
        sa.CheckConstraint("length(trim(goals)) >= 3", name="ck_nursing_care_plan_goals"),
        sa.CheckConstraint("length(trim(interventions)) >= 3", name="ck_nursing_care_plan_interventions"),
    )
    op.create_index("ix_nursing_care_plan_encounter", "nursing_care_plans", ["hospital_id", "encounter_id", "status"])

    op.create_table(
        "nursing_care_plan_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("care_plan_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("evaluation_note", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "care_plan_id"], ["nursing_care_plans.hospital_id", "nursing_care_plans.id"], name="fk_nursing_care_plan_review_plan"),
        sa.CheckConstraint("outcome IN ('ongoing', 'achieved', 'partially_achieved', 'not_achieved', 'escalated')", name="ck_nursing_care_plan_review_outcome"),
        sa.CheckConstraint("length(trim(evaluation_note)) >= 3", name="ck_nursing_care_plan_review_note"),
    )
    op.create_index("ix_nursing_care_plan_review_plan", "nursing_care_plan_reviews", ["hospital_id", "care_plan_id", "reviewed_at"])

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
    op.drop_index("ix_nursing_care_plan_review_plan", table_name="nursing_care_plan_reviews")
    op.drop_table("nursing_care_plan_reviews")
    op.drop_index("ix_nursing_care_plan_encounter", table_name="nursing_care_plans")
    op.drop_table("nursing_care_plans")
    op.drop_index("ix_nursing_note_encounter", table_name="nursing_notes")
    op.drop_table("nursing_notes")
    op.drop_index("ix_nursing_observation_encounter", table_name="nursing_observations")
    op.drop_table("nursing_observations")
    op.drop_index("ix_nursing_assessment_encounter", table_name="nursing_assessments")
    op.drop_table("nursing_assessments")
