"""Create OPD visit, triage, consultation and diagnosis workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0017_opd_workflows"
down_revision = "0016_patient_consent_basis"
branch_labels = None
depends_on = None

TABLES = ("opd_visits", "opd_triage_assessments", "opd_consultation_notes", "opd_diagnoses")


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_department_hospital_id_id", "departments", ["hospital_id", "id"]
    )
    op.create_unique_constraint(
        "uq_encounter_hospital_id_id", "encounters", ["hospital_id", "id"]
    )

    op.create_table(
        "opd_visits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("queue_token", sa.String(12), nullable=False),
        sa.Column("visit_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="registered"),
        sa.Column("priority", sa.String(24), nullable=False, server_default="standard"),
        sa.Column("arrival_at", sa.DateTime(timezone=True)),
        sa.Column("triage_at", sa.DateTime(timezone=True)),
        sa.Column("consultation_started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_clinician_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("disposition", sa.String(32)),
        sa.Column("disposition_note", sa.Text()),
        sa.Column("closed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"],
            name="fk_opd_visit_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "encounter_id"], ["encounters.hospital_id", "encounters.id"],
            name="fk_opd_visit_encounter",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"],
            name="fk_opd_visit_department",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_opd_visit_hospital_id_id"),
        sa.UniqueConstraint("hospital_id", "encounter_id", name="uq_opd_visit_encounter"),
        sa.UniqueConstraint("hospital_id", "visit_date", "queue_token", name="uq_opd_visit_queue_token"),
        sa.CheckConstraint(
            "visit_type IN ('walk_in', 'appointment', 'referral', 'transfer')",
            name="ck_opd_visit_type",
        ),
        sa.CheckConstraint(
            "status IN ('registered', 'arrived', 'waiting', 'in_consultation', "
            "'completed', 'closed', 'cancelled', 'left_without_being_seen')",
            name="ck_opd_visit_status",
        ),
        sa.CheckConstraint(
            "priority IN ('emergency', 'very_urgent', 'urgent', 'standard', 'non_urgent')",
            name="ck_opd_visit_priority",
        ),
        sa.CheckConstraint(
            "disposition IS NULL OR disposition IN "
            "('discharged', 'admission_requested', 'referred', 'transfer_requested', 'left_without_being_seen')",
            name="ck_opd_visit_disposition",
        ),
    )
    op.create_index(
        "ix_opd_queue", "opd_visits",
        ["hospital_id", "department_id", "visit_date", "status", "priority"],
    )
    op.create_index(
        "ix_opd_patient_history", "opd_visits",
        ["hospital_id", "patient_id", "created_at"],
    )

    op.create_table(
        "opd_triage_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("assessed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("triage_level", sa.String(24), nullable=False),
        sa.Column("chief_complaint", sa.Text(), nullable=False),
        sa.Column("red_flag_present", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("red_flag_note", sa.Text()),
        sa.Column("heart_rate", sa.Numeric(6, 2)),
        sa.Column("respiratory_rate", sa.Numeric(6, 2)),
        sa.Column("temperature_c", sa.Numeric(4, 1)),
        sa.Column("systolic_bp", sa.Numeric(6, 2)),
        sa.Column("diastolic_bp", sa.Numeric(6, 2)),
        sa.Column("spo2_percent", sa.Numeric(5, 2)),
        sa.Column("weight_kg", sa.Numeric(6, 2)),
        sa.Column("height_cm", sa.Numeric(6, 2)),
        sa.Column("pain_score", sa.SmallInteger()),
        sa.Column("consciousness_level", sa.String(12)),
        sa.Column("clinical_notes", sa.Text()),
        sa.Column("assessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "visit_id"], ["opd_visits.hospital_id", "opd_visits.id"],
            name="fk_opd_triage_visit", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("hospital_id", "visit_id", name="uq_opd_triage_visit"),
        sa.CheckConstraint(
            "triage_level IN ('emergency', 'very_urgent', 'urgent', 'standard', 'non_urgent')",
            name="ck_opd_triage_level",
        ),
        sa.CheckConstraint("heart_rate IS NULL OR heart_rate BETWEEN 1 AND 300", name="ck_opd_triage_hr"),
        sa.CheckConstraint("respiratory_rate IS NULL OR respiratory_rate BETWEEN 1 AND 100", name="ck_opd_triage_rr"),
        sa.CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_opd_triage_temp"),
        sa.CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_opd_triage_systolic"),
        sa.CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_opd_triage_diastolic"),
        sa.CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_opd_triage_spo2"),
        sa.CheckConstraint("weight_kg IS NULL OR weight_kg BETWEEN 0.2 AND 500", name="ck_opd_triage_weight"),
        sa.CheckConstraint("height_cm IS NULL OR height_cm BETWEEN 20 AND 250", name="ck_opd_triage_height"),
        sa.CheckConstraint("pain_score IS NULL OR pain_score BETWEEN 0 AND 10", name="ck_opd_triage_pain"),
        sa.CheckConstraint(
            "red_flag_present = false OR (red_flag_note IS NOT NULL AND length(trim(red_flag_note)) >= 3)",
            name="ck_opd_triage_red_flag_note",
        ),
    )
    op.create_index(
        "ix_opd_triage_hospital_visit", "opd_triage_assessments", ["hospital_id", "visit_id"]
    )

    op.create_table(
        "opd_consultation_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("clinician_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subjective", sa.Text()),
        sa.Column("objective", sa.Text()),
        sa.Column("assessment", sa.Text(), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("follow_up", sa.Text()),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "visit_id"], ["opd_visits.hospital_id", "opd_visits.id"],
            name="fk_opd_consultation_visit", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("hospital_id", "visit_id", name="uq_opd_consultation_visit"),
        sa.CheckConstraint("length(trim(assessment)) >= 3", name="ck_opd_consultation_assessment"),
        sa.CheckConstraint("length(trim(plan)) >= 3", name="ck_opd_consultation_plan"),
    )
    op.create_index(
        "ix_opd_consultation_hospital_visit", "opd_consultation_notes", ["hospital_id", "visit_id"]
    )

    op.create_table(
        "opd_diagnoses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("diagnosis_text", sa.String(500), nullable=False),
        sa.Column("concept_id", sa.Uuid(), sa.ForeignKey("clinical_concepts.id")),
        sa.Column("certainty", sa.String(24), nullable=False, server_default="provisional"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "visit_id"], ["opd_visits.hospital_id", "opd_visits.id"],
            name="fk_opd_diagnosis_visit", ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "certainty IN ('suspected', 'provisional', 'confirmed', 'ruled_out')",
            name="ck_opd_diagnosis_certainty",
        ),
    )
    op.create_index(
        "ix_opd_diagnosis_hospital_visit", "opd_diagnoses", ["hospital_id", "visit_id"]
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
    op.drop_index("ix_opd_diagnosis_hospital_visit", table_name="opd_diagnoses")
    op.drop_table("opd_diagnoses")
    op.drop_index("ix_opd_consultation_hospital_visit", table_name="opd_consultation_notes")
    op.drop_table("opd_consultation_notes")
    op.drop_index("ix_opd_triage_hospital_visit", table_name="opd_triage_assessments")
    op.drop_table("opd_triage_assessments")
    op.drop_index("ix_opd_patient_history", table_name="opd_visits")
    op.drop_index("ix_opd_queue", table_name="opd_visits")
    op.drop_table("opd_visits")
    op.drop_constraint("uq_encounter_hospital_id_id", "encounters", type_="unique")
    op.drop_constraint("uq_department_hospital_id_id", "departments", type_="unique")
