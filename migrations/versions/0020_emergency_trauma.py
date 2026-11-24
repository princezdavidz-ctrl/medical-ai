"""Create emergency department visit, triage and care records."""

from alembic import op
import sqlalchemy as sa

revision = "0020_emergency_trauma"
down_revision = "0019_inpatient_ward"
branch_labels = None
depends_on = None

TABLES = (
    "emergency_visits",
    "emergency_triage_assessments",
    "emergency_care_events",
    "emergency_notes",
)


def upgrade() -> None:
    op.create_table(
        "emergency_visits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("arrival_mode", sa.String(24), nullable=False),
        sa.Column("arrival_note", sa.String(1000)),
        sa.Column("status", sa.String(32), nullable=False, server_default="arrived"),
        sa.Column("priority", sa.String(24), nullable=False, server_default="untriaged"),
        sa.Column("arrival_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("triaged_at", sa.DateTime(timezone=True)),
        sa.Column("treatment_started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_clinician_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("disposition", sa.String(32)),
        sa.Column("disposition_note", sa.Text()),
        sa.Column("closed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_emergency_visit_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_emergency_visit_encounter_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_emergency_visit_department"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_emergency_visit_hospital_id_id"),
        sa.UniqueConstraint("hospital_id", "encounter_id", name="uq_emergency_visit_encounter"),
        sa.CheckConstraint("arrival_mode IN ('walk_in', 'ambulance', 'referral', 'police', 'other')", name="ck_emergency_visit_arrival_mode"),
        sa.CheckConstraint("status IN ('arrived', 'waiting', 'in_treatment', 'completed', 'closed', 'left_without_being_seen', 'cancelled')", name="ck_emergency_visit_status"),
        sa.CheckConstraint("priority IN ('untriaged', 'resuscitation', 'emergent', 'urgent', 'less_urgent', 'non_urgent')", name="ck_emergency_visit_priority"),
        sa.CheckConstraint("disposition IS NULL OR disposition IN ('discharged', 'admission_requested', 'referred', 'transfer_requested', 'left_without_being_seen')", name="ck_emergency_visit_disposition"),
    )
    op.create_index(
        "uq_emergency_active_patient", "emergency_visits",
        ["hospital_id", "patient_id"], unique=True,
        postgresql_where=sa.text("status IN ('arrived', 'waiting', 'in_treatment')"),
    )
    op.create_index(
        "ix_emergency_queue", "emergency_visits",
        ["hospital_id", "department_id", "status", "priority", "arrival_at"],
    )

    op.create_table(
        "emergency_triage_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
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
        sa.Column("pain_score", sa.Integer()),
        sa.Column("consciousness_level", sa.String(16)),
        sa.Column("clinical_notes", sa.Text()),
        sa.Column("assessed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "visit_id"], ["emergency_visits.hospital_id", "emergency_visits.id"], name="fk_emergency_triage_visit"),
        sa.UniqueConstraint("hospital_id", "visit_id", "revision", name="uq_emergency_triage_revision"),
        sa.CheckConstraint("triage_level IN ('resuscitation', 'emergent', 'urgent', 'less_urgent', 'non_urgent')", name="ck_emergency_triage_level"),
        sa.CheckConstraint("revision >= 1", name="ck_emergency_triage_revision"),
        sa.CheckConstraint("pain_score IS NULL OR pain_score BETWEEN 0 AND 10", name="ck_emergency_triage_pain"),
        sa.CheckConstraint("heart_rate IS NULL OR heart_rate BETWEEN 1 AND 300", name="ck_emergency_triage_hr"),
        sa.CheckConstraint("respiratory_rate IS NULL OR respiratory_rate BETWEEN 1 AND 100", name="ck_emergency_triage_rr"),
        sa.CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_emergency_triage_temp"),
        sa.CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_emergency_triage_systolic"),
        sa.CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_emergency_triage_diastolic"),
        sa.CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_emergency_triage_spo2"),
        sa.CheckConstraint("red_flag_present = false OR (red_flag_note IS NOT NULL AND length(trim(red_flag_note)) >= 3)", name="ck_emergency_triage_red_flag_note"),
    )

    op.create_table(
        "emergency_care_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("performed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "visit_id"], ["emergency_visits.hospital_id", "emergency_visits.id"], name="fk_emergency_event_visit"),
        sa.CheckConstraint("event_type IN ('assessment', 'intervention', 'procedure', 'reassessment', 'handover')", name="ck_emergency_event_type"),
        sa.CheckConstraint("length(trim(description)) >= 3", name="ck_emergency_event_description"),
    )
    op.create_index("ix_emergency_event_visit", "emergency_care_events", ["hospital_id", "visit_id", "performed_at"])

    op.create_table(
        "emergency_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_type", sa.String(24), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "visit_id"], ["emergency_visits.hospital_id", "emergency_visits.id"], name="fk_emergency_note_visit"),
        sa.CheckConstraint("note_type IN ('progress', 'handover', 'incident', 'discharge', 'other')", name="ck_emergency_note_type"),
        sa.CheckConstraint("length(trim(note_text)) >= 3", name="ck_emergency_note_text"),
    )
    op.create_index("ix_emergency_note_visit", "emergency_notes", ["hospital_id", "visit_id", "signed_at"])

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
    op.drop_index("ix_emergency_note_visit", table_name="emergency_notes")
    op.drop_table("emergency_notes")
    op.drop_index("ix_emergency_event_visit", table_name="emergency_care_events")
    op.drop_table("emergency_care_events")
    op.drop_table("emergency_triage_assessments")
    op.drop_index("ix_emergency_queue", table_name="emergency_visits")
    op.drop_index("uq_emergency_active_patient", table_name="emergency_visits")
    op.drop_table("emergency_visits")
