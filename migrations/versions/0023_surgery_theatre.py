"""Create operating theatre and surgical case workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0023_surgery_theatre"
down_revision = "0022_icu_workflows"
branch_labels = None
depends_on = None

TABLES = (
    "theatre_rooms",
    "surgical_cases",
    "surgical_safety_checklists",
    "anesthesia_records",
    "surgical_events",
    "surgical_notes",
)


def upgrade() -> None:
    op.create_table(
        "theatre_rooms",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("theatre_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_theatre_room_department"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_theatre_room_hospital_id_id"),
        sa.UniqueConstraint("hospital_id", "code", name="uq_theatre_room_hospital_code"),
        sa.CheckConstraint("theatre_type IN ('general', 'orthopedic', 'cardiac', 'obstetric', 'neurosurgical', 'other')", name="ck_theatre_room_type"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name="ck_theatre_room_status"),
    )

    op.create_table(
        "surgical_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("theatre_room_id", sa.Uuid(), nullable=False),
        sa.Column("surgeon_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("planned_procedure", sa.String(2000), nullable=False),
        sa.Column("urgency", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="scheduled"),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_started_at", sa.DateTime(timezone=True)),
        sa.Column("actual_ended_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_reason", sa.Text()),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_surgical_case_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_surgical_case_encounter_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "theatre_room_id"], ["theatre_rooms.hospital_id", "theatre_rooms.id"], name="fk_surgical_case_theatre"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_surgical_case_hospital_id_id"),
        sa.CheckConstraint("urgency IN ('elective', 'urgent', 'emergency')", name="ck_surgical_case_urgency"),
        sa.CheckConstraint("status IN ('scheduled', 'in_progress', 'recovery', 'completed', 'cancelled')", name="ck_surgical_case_status"),
        sa.CheckConstraint("scheduled_end_at > scheduled_start_at", name="ck_surgical_case_schedule"),
        sa.CheckConstraint("length(trim(planned_procedure)) >= 3", name="ck_surgical_case_procedure"),
        sa.CheckConstraint("status != 'cancelled' OR (cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL)", name="ck_surgical_case_cancelled_fields"),
    )
    op.create_index("ix_surgical_case_theatre_schedule", "surgical_cases", ["hospital_id", "theatre_room_id", "status", "scheduled_start_at"])
    op.create_index("ix_surgical_case_encounter", "surgical_cases", ["hospital_id", "encounter_id", "status"])

    op.create_table(
        "surgical_safety_checklists",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("surgical_case_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("patient_identity_confirmed", sa.Boolean(), nullable=False),
        sa.Column("procedure_confirmed", sa.Boolean(), nullable=False),
        sa.Column("site_marking_applicable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("site_confirmed", sa.Boolean(), nullable=False),
        sa.Column("counts_applicable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("consent_verified", sa.Boolean(), nullable=False),
        sa.Column("allergies_reviewed", sa.Boolean(), nullable=False),
        sa.Column("anesthesia_safety_confirmed", sa.Boolean(), nullable=False),
        sa.Column("equipment_ready", sa.Boolean(), nullable=False),
        sa.Column("counts_confirmed", sa.Boolean(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "surgical_case_id"], ["surgical_cases.hospital_id", "surgical_cases.id"], name="fk_surgical_checklist_case"),
        sa.UniqueConstraint("hospital_id", "surgical_case_id", "phase", "revision", name="uq_surgical_checklist_revision"),
        sa.CheckConstraint("phase IN ('sign_in', 'time_out', 'sign_out')", name="ck_surgical_checklist_phase"),
        sa.CheckConstraint("revision >= 1", name="ck_surgical_checklist_revision"),
    )
    op.create_index("ix_surgical_checklist_case", "surgical_safety_checklists", ["hospital_id", "surgical_case_id", "phase", "revision"])

    op.create_table(
        "anesthesia_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("surgical_case_id", sa.Uuid(), nullable=False),
        sa.Column("anesthesia_provider_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("anesthesia_type", sa.String(24), nullable=False),
        sa.Column("asa_class", sa.Integer(), nullable=False),
        sa.Column("airway_method", sa.String(160)),
        sa.Column("pre_anesthesia_assessment", sa.Text(), nullable=False),
        sa.Column("intraoperative_notes", sa.Text()),
        sa.Column("complications", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["hospital_id", "surgical_case_id"], ["surgical_cases.hospital_id", "surgical_cases.id"], name="fk_anesthesia_record_case"),
        sa.UniqueConstraint("hospital_id", "surgical_case_id", name="uq_anesthesia_record_case"),
        sa.CheckConstraint("anesthesia_type IN ('general', 'regional', 'local', 'sedation', 'combined')", name="ck_anesthesia_record_type"),
        sa.CheckConstraint("asa_class BETWEEN 1 AND 5", name="ck_anesthesia_record_asa"),
        sa.CheckConstraint("ended_at IS NULL OR ended_at > started_at", name="ck_anesthesia_record_time"),
        sa.CheckConstraint("length(trim(pre_anesthesia_assessment)) >= 3", name="ck_anesthesia_assessment"),
    )

    op.create_table(
        "surgical_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("surgical_case_id", sa.Uuid(), nullable=False),
        sa.Column("performed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "surgical_case_id"], ["surgical_cases.hospital_id", "surgical_cases.id"], name="fk_surgical_event_case"),
        sa.CheckConstraint("event_type IN ('incision', 'procedure_step', 'specimen', 'count_check', 'closure', 'complication', 'handover', 'other')", name="ck_surgical_event_type"),
        sa.CheckConstraint("length(trim(description)) >= 3", name="ck_surgical_event_description"),
    )
    op.create_index("ix_surgical_event_case", "surgical_events", ["hospital_id", "surgical_case_id", "performed_at"])

    op.create_table(
        "surgical_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("surgical_case_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_type", sa.String(24), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "surgical_case_id"], ["surgical_cases.hospital_id", "surgical_cases.id"], name="fk_surgical_note_case"),
        sa.CheckConstraint("note_type IN ('operative', 'post_op', 'handover', 'incident', 'other')", name="ck_surgical_note_type"),
        sa.CheckConstraint("length(trim(note_text)) >= 3", name="ck_surgical_note_text"),
    )
    op.create_index("ix_surgical_note_case", "surgical_notes", ["hospital_id", "surgical_case_id", "signed_at"])

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
    op.drop_index("ix_surgical_note_case", table_name="surgical_notes")
    op.drop_table("surgical_notes")
    op.drop_index("ix_surgical_event_case", table_name="surgical_events")
    op.drop_table("surgical_events")
    op.drop_table("anesthesia_records")
    op.drop_index("ix_surgical_checklist_case", table_name="surgical_safety_checklists")
    op.drop_table("surgical_safety_checklists")
    op.drop_index("ix_surgical_case_encounter", table_name="surgical_cases")
    op.drop_index("ix_surgical_case_theatre_schedule", table_name="surgical_cases")
    op.drop_table("surgical_cases")
    op.drop_table("theatre_rooms")
