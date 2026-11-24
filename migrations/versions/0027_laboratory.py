"""Create governed laboratory catalog, order, specimen and result workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0027_laboratory"
down_revision = "0026_pediatrics"
branch_labels = None
depends_on = None

TABLES = (
    "laboratory_test_definitions",
    "laboratory_orders",
    "laboratory_specimens",
    "laboratory_results",
    "laboratory_critical_acknowledgements",
)


def upgrade() -> None:
    op.create_table(
        "laboratory_test_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("specimen_type", sa.String(100), nullable=False),
        sa.Column("method", sa.String(160)),
        sa.Column("result_unit", sa.String(80)),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_lab_test_definition_department",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_lab_test_definition_hospital_id"),
        sa.UniqueConstraint("hospital_id", "code", name="uq_lab_test_definition_code"),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_lab_test_definition_status"),
        sa.CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL) OR "
            "(status IN ('active', 'retired') AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_lab_test_definition_approval_state",
        ),
        sa.CheckConstraint(
            "approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id",
            name="ck_lab_test_definition_two_person",
        ),
    )
    op.create_index(
        "ix_lab_test_definition_department_status",
        "laboratory_test_definitions",
        ["hospital_id", "department_id", "status"],
    )

    op.create_table(
        "laboratory_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("ordering_department_id", sa.Uuid(), nullable=False),
        sa.Column("laboratory_department_id", sa.Uuid(), nullable=False),
        sa.Column("test_definition_id", sa.Uuid(), nullable=False),
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
            name="fk_lab_order_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_lab_order_encounter_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "ordering_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_lab_order_ordering_department",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "laboratory_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_lab_order_laboratory_department",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "test_definition_id"],
            ["laboratory_test_definitions.hospital_id", "laboratory_test_definitions.id"],
            name="fk_lab_order_test_definition",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_lab_order_hospital_id"),
        sa.CheckConstraint("status IN ('ordered', 'in_progress', 'completed', 'cancelled')", name="ck_lab_order_status"),
        sa.CheckConstraint("priority IN ('routine', 'urgent', 'stat')", name="ck_lab_order_priority"),
        sa.CheckConstraint(
            "(status = 'cancelled' AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL) OR "
            "(status != 'cancelled' AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL AND cancellation_reason IS NULL)",
            name="ck_lab_order_cancellation_state",
        ),
        sa.CheckConstraint(
            "status != 'completed' OR completed_at IS NOT NULL",
            name="ck_lab_order_completion_timestamp",
        ),
    )
    op.create_index(
        "ix_lab_order_patient_encounter",
        "laboratory_orders",
        ["hospital_id", "patient_id", "encounter_id"],
    )
    op.create_index(
        "ix_lab_order_lab_queue",
        "laboratory_orders",
        ["hospital_id", "laboratory_department_id", "status", "ordered_at"],
    )

    op.create_table(
        "laboratory_specimens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("accession_number", sa.String(100), nullable=False),
        sa.Column("specimen_type", sa.String(100), nullable=False),
        sa.Column("collected_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="collected"),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.ForeignKeyConstraint(
            ["hospital_id", "order_id"],
            ["laboratory_orders.hospital_id", "laboratory_orders.id"],
            name="fk_lab_specimen_order",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_lab_specimen_hospital_id"),
        sa.UniqueConstraint("hospital_id", "accession_number", name="uq_lab_specimen_accession"),
        sa.CheckConstraint(
            "status IN ('collected', 'received', 'processing', 'rejected', 'completed')",
            name="ck_lab_specimen_status",
        ),
        sa.CheckConstraint(
            "(status = 'rejected' AND rejected_at IS NOT NULL AND rejection_reason IS NOT NULL) OR "
            "(status != 'rejected' AND rejected_at IS NULL AND rejection_reason IS NULL)",
            name="ck_lab_specimen_rejection_state",
        ),
        sa.CheckConstraint(
            "status NOT IN ('received', 'processing', 'completed') OR received_at IS NOT NULL",
            name="ck_lab_specimen_received_state",
        ),
        sa.CheckConstraint(
            "status NOT IN ('processing', 'completed') OR processing_started_at IS NOT NULL",
            name="ck_lab_specimen_processing_state",
        ),
    )
    op.create_index(
        "ix_lab_specimen_order_time",
        "laboratory_specimens",
        ["hospital_id", "order_id", "collected_at"],
    )
    op.create_index(
        "uq_lab_specimen_one_active_per_order",
        "laboratory_specimens",
        ["hospital_id", "order_id"],
        unique=True,
        postgresql_where=sa.text("status != 'rejected'"),
    )

    op.create_table(
        "laboratory_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("specimen_id", sa.Uuid(), nullable=False),
        sa.Column("entered_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("value_text", sa.Text()),
        sa.Column("value_numeric", sa.Numeric(20, 8)),
        sa.Column("unit", sa.String(80)),
        sa.Column("abnormality", sa.String(24), nullable=False, server_default="not_flagged"),
        sa.Column("interpretation_note", sa.Text()),
        sa.Column("critical_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("critical_note", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False, server_default="preliminary"),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("entered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "specimen_id"],
            ["laboratory_specimens.hospital_id", "laboratory_specimens.id"],
            name="fk_lab_result_specimen",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_lab_result_hospital_id"),
        sa.UniqueConstraint("hospital_id", "specimen_id", name="uq_lab_result_specimen"),
        sa.CheckConstraint(
            "(value_text IS NOT NULL AND value_numeric IS NULL) OR "
            "(value_text IS NULL AND value_numeric IS NOT NULL)",
            name="ck_lab_result_exactly_one_value",
        ),
        sa.CheckConstraint(
            "abnormality IN ('not_flagged', 'low', 'high', 'critical', 'not_applicable')",
            name="ck_lab_result_abnormality",
        ),
        sa.CheckConstraint("status IN ('preliminary', 'final')", name="ck_lab_result_status"),
        sa.CheckConstraint(
            "(status = 'preliminary' AND verified_by_user_id IS NULL AND verified_at IS NULL) OR "
            "(status = 'final' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_lab_result_verification_state",
        ),
        sa.CheckConstraint(
            "verified_by_user_id IS NULL OR verified_by_user_id != entered_by_user_id",
            name="ck_lab_result_two_person_verification",
        ),
        sa.CheckConstraint(
            "critical_flag = false OR (critical_note IS NOT NULL AND length(trim(critical_note)) >= 3)",
            name="ck_lab_result_critical_note",
        ),
        sa.CheckConstraint(
            "abnormality != 'critical' OR critical_flag = true",
            name="ck_lab_result_critical_abnormality_flag",
        ),
    )
    op.create_index(
        "ix_lab_result_status_time",
        "laboratory_results",
        ["hospital_id", "status", "entered_at"],
    )

    op.create_table(
        "laboratory_critical_acknowledgements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("result_id", sa.Uuid(), nullable=False),
        sa.Column("acknowledged_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("acknowledgement_note", sa.Text(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "result_id"],
            ["laboratory_results.hospital_id", "laboratory_results.id"],
            name="fk_lab_critical_ack_result",
        ),
        sa.UniqueConstraint("hospital_id", "result_id", name="uq_lab_critical_ack_result"),
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
    op.drop_table("laboratory_critical_acknowledgements")
    op.drop_index("ix_lab_result_status_time", table_name="laboratory_results")
    op.drop_table("laboratory_results")
    op.drop_index("uq_lab_specimen_one_active_per_order", table_name="laboratory_specimens")
    op.drop_index("ix_lab_specimen_order_time", table_name="laboratory_specimens")
    op.drop_table("laboratory_specimens")
    op.drop_index("ix_lab_order_lab_queue", table_name="laboratory_orders")
    op.drop_index("ix_lab_order_patient_encounter", table_name="laboratory_orders")
    op.drop_table("laboratory_orders")
    op.drop_index("ix_lab_test_definition_department_status", table_name="laboratory_test_definitions")
    op.drop_table("laboratory_test_definitions")
