"""Create radiology and medical imaging order, study and reporting workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0028_radiology"
down_revision = "0027_laboratory"
branch_labels = None
depends_on = None

TABLES = (
    "imaging_procedure_definitions",
    "imaging_orders",
    "imaging_studies",
    "imaging_reports",
    "imaging_critical_acknowledgements",
)


def upgrade() -> None:
    op.create_table(
        "imaging_procedure_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("modality", sa.String(24), nullable=False),
        sa.Column("body_region", sa.String(120), nullable=False),
        sa.Column("contrast_policy", sa.String(24), nullable=False, server_default="not_applicable"),
        sa.Column("preparation_instructions", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("retired_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.Column("retirement_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_imaging_definition_department",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_imaging_definition_hospital_id"),
        sa.UniqueConstraint("hospital_id", "code", name="uq_imaging_definition_code"),
        sa.CheckConstraint(
            "modality IN ('xray', 'ct', 'mri', 'ultrasound', 'mammography', 'fluoroscopy', 'nuclear_medicine', 'pet', 'other')",
            name="ck_imaging_definition_modality",
        ),
        sa.CheckConstraint(
            "contrast_policy IN ('none', 'optional', 'required', 'not_applicable')",
            name="ck_imaging_definition_contrast",
        ),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_imaging_definition_status"),
        sa.CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'active' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NOT NULL AND retired_at IS NOT NULL "
            "AND retirement_reason IS NOT NULL AND length(trim(retirement_reason)) >= 3)",
            name="ck_imaging_definition_approval_state",
        ),
        sa.CheckConstraint(
            "approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id",
            name="ck_imaging_definition_two_person",
        ),
        sa.CheckConstraint(
            "length(trim(code)) >= 2 AND length(trim(name)) >= 2 "
            "AND length(trim(body_region)) >= 2",
            name="ck_imaging_definition_text",
        ),
    )
    op.create_index(
        "ix_imaging_definition_department_status",
        "imaging_procedure_definitions",
        ["hospital_id", "department_id", "status"],
    )

    op.create_table(
        "imaging_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("ordering_department_id", sa.Uuid(), nullable=False),
        sa.Column("imaging_department_id", sa.Uuid(), nullable=False),
        sa.Column("procedure_definition_id", sa.Uuid(), nullable=False),
        sa.Column("ordered_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False, server_default="routine"),
        sa.Column("clinical_indication", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="ordered"),
        sa.Column("ordered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_reason", sa.Text()),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_imaging_order_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_imaging_order_encounter_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "ordering_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_imaging_order_ordering_department",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "imaging_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_imaging_order_imaging_department",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "procedure_definition_id"],
            ["imaging_procedure_definitions.hospital_id", "imaging_procedure_definitions.id"],
            name="fk_imaging_order_definition",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_imaging_order_hospital_id"),
        sa.CheckConstraint("status IN ('ordered', 'scheduled', 'in_progress', 'completed', 'cancelled')", name="ck_imaging_order_status"),
        sa.CheckConstraint("priority IN ('routine', 'urgent', 'stat')", name="ck_imaging_order_priority"),
        sa.CheckConstraint("length(trim(clinical_indication)) >= 3", name="ck_imaging_order_indication"),
        sa.CheckConstraint(
            "(status = 'cancelled' AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL "
            "AND length(trim(cancellation_reason)) >= 3) OR "
            "(status != 'cancelled' AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL AND cancellation_reason IS NULL)",
            name="ck_imaging_order_cancellation_state",
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status != 'completed' AND completed_at IS NULL)",
            name="ck_imaging_order_completion_state",
        ),
    )
    op.create_index(
        "ix_imaging_order_patient_encounter",
        "imaging_orders",
        ["hospital_id", "patient_id", "encounter_id"],
    )
    op.create_index(
        "ix_imaging_order_queue",
        "imaging_orders",
        ["hospital_id", "imaging_department_id", "status", "ordered_at"],
    )

    op.create_table(
        "imaging_studies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("accession_number", sa.String(100), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("performed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False, server_default="scheduled"),
        sa.Column("pacs_system_reference", sa.String(160)),
        sa.Column("pacs_study_uid", sa.String(100)),
        sa.ForeignKeyConstraint(
            ["hospital_id", "order_id"],
            ["imaging_orders.hospital_id", "imaging_orders.id"],
            name="fk_imaging_study_order",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_imaging_study_hospital_id"),
        sa.UniqueConstraint("hospital_id", "order_id", name="uq_imaging_study_order"),
        sa.UniqueConstraint("hospital_id", "accession_number", name="uq_imaging_study_accession"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'completed', 'cancelled')",
            name="ck_imaging_study_status",
        ),
        sa.CheckConstraint(
            "(status = 'scheduled' AND scheduled_at IS NOT NULL AND started_at IS NULL "
            "AND completed_at IS NULL AND cancelled_at IS NULL AND performed_by_user_id IS NULL) OR "
            "(status = 'in_progress' AND scheduled_at IS NOT NULL AND started_at IS NOT NULL "
            "AND completed_at IS NULL AND cancelled_at IS NULL AND performed_by_user_id IS NOT NULL) OR "
            "(status = 'completed' AND scheduled_at IS NOT NULL AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL AND cancelled_at IS NULL AND performed_by_user_id IS NOT NULL) OR "
            "(status = 'cancelled' AND scheduled_at IS NOT NULL AND started_at IS NULL "
            "AND completed_at IS NULL AND cancelled_at IS NOT NULL AND performed_by_user_id IS NULL)",
            name="ck_imaging_study_workflow_timestamps",
        ),
        sa.CheckConstraint("length(trim(accession_number)) >= 2", name="ck_imaging_study_accession_text"),
        sa.CheckConstraint(
            "pacs_study_uid IS NULL OR pacs_system_reference IS NOT NULL",
            name="ck_imaging_study_pacs_reference_pair",
        ),
    )
    op.create_index(
        "ix_imaging_study_queue",
        "imaging_studies",
        ["hospital_id", "status", "scheduled_at"],
    )

    op.create_table(
        "imaging_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("entered_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("impression", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="preliminary"),
        sa.Column("critical_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("critical_note", sa.Text()),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("entered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "study_id"],
            ["imaging_studies.hospital_id", "imaging_studies.id"],
            name="fk_imaging_report_study",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_imaging_report_hospital_id"),
        sa.UniqueConstraint("hospital_id", "study_id", name="uq_imaging_report_study"),
        sa.CheckConstraint("status IN ('preliminary', 'final')", name="ck_imaging_report_status"),
        sa.CheckConstraint(
            "(status = 'preliminary' AND verified_by_user_id IS NULL AND verified_at IS NULL) OR "
            "(status = 'final' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_imaging_report_verification_state",
        ),
        sa.CheckConstraint(
            "verified_by_user_id IS NULL OR verified_by_user_id != entered_by_user_id",
            name="ck_imaging_report_two_person",
        ),
        sa.CheckConstraint(
            "length(trim(findings)) >= 3 AND length(trim(impression)) >= 3",
            name="ck_imaging_report_content",
        ),
        sa.CheckConstraint(
            "(critical_flag = true AND critical_note IS NOT NULL AND length(trim(critical_note)) >= 3) OR "
            "(critical_flag = false AND critical_note IS NULL)",
            name="ck_imaging_report_critical_note",
        ),
    )
    op.create_index(
        "ix_imaging_report_status_time",
        "imaging_reports",
        ["hospital_id", "status", "entered_at"],
    )

    op.create_table(
        "imaging_critical_acknowledgements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("acknowledged_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("acknowledgement_note", sa.Text(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "report_id"],
            ["imaging_reports.hospital_id", "imaging_reports.id"],
            name="fk_imaging_critical_ack_report",
        ),
        sa.UniqueConstraint("hospital_id", "report_id", name="uq_imaging_critical_ack_report"),
        sa.CheckConstraint("length(trim(acknowledgement_note)) >= 3", name="ck_imaging_critical_ack_note"),
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
    op.drop_table("imaging_critical_acknowledgements")
    op.drop_index("ix_imaging_report_status_time", table_name="imaging_reports")
    op.drop_table("imaging_reports")
    op.drop_index("ix_imaging_study_queue", table_name="imaging_studies")
    op.drop_table("imaging_studies")
    op.drop_index("ix_imaging_order_queue", table_name="imaging_orders")
    op.drop_index("ix_imaging_order_patient_encounter", table_name="imaging_orders")
    op.drop_table("imaging_orders")
    op.drop_index("ix_imaging_definition_department_status", table_name="imaging_procedure_definitions")
    op.drop_table("imaging_procedure_definitions")
