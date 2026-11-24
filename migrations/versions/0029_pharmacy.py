"""Create governed medication catalog, prescription review and dispense workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0029_pharmacy"
down_revision = "0028_radiology"
branch_labels = None
depends_on = None

TABLES = (
    "medication_definitions",
    "medication_orders",
    "medication_order_review_events",
    "medication_dispenses",
)


def upgrade() -> None:
    op.create_table(
        "medication_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("generic_name", sa.String(180), nullable=False),
        sa.Column("brand_name", sa.String(180)),
        sa.Column("active_ingredient", sa.String(180), nullable=False),
        sa.Column("strength_label", sa.String(100), nullable=False),
        sa.Column("dosage_form", sa.String(100), nullable=False),
        sa.Column("default_route", sa.String(32)),
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
            name="fk_medication_definition_department",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_medication_definition_hospital_id"),
        sa.UniqueConstraint("hospital_id", "code", name="uq_medication_definition_code"),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_medication_definition_status"),
        sa.CheckConstraint(
            "default_route IS NULL OR default_route IN ('oral', 'topical', 'inhalation', "
            "'intravenous', 'intramuscular', 'subcutaneous', 'rectal', 'ophthalmic', "
            "'otic', 'nasal', 'transdermal', 'other')",
            name="ck_medication_definition_default_route",
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'active' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NOT NULL AND retired_at IS NOT NULL "
            "AND retirement_reason IS NOT NULL AND length(trim(retirement_reason)) >= 3)",
            name="ck_medication_definition_approval_state",
        ),
        sa.CheckConstraint(
            "approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id",
            name="ck_medication_definition_two_person",
        ),
        sa.CheckConstraint(
            "length(trim(code)) >= 2 AND length(trim(generic_name)) >= 2 "
            "AND length(trim(active_ingredient)) >= 2 AND length(trim(strength_label)) >= 1 "
            "AND length(trim(dosage_form)) >= 2",
            name="ck_medication_definition_text",
        ),
    )
    op.create_index(
        "ix_medication_definition_department_status",
        "medication_definitions",
        ["hospital_id", "department_id", "status"],
    )

    op.create_table(
        "medication_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("ordering_department_id", sa.Uuid(), nullable=False),
        sa.Column("pharmacy_department_id", sa.Uuid(), nullable=False),
        sa.Column("medication_definition_id", sa.Uuid(), nullable=False),
        sa.Column("prescribed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("dose_text", sa.String(160), nullable=False),
        sa.Column("route", sa.String(32), nullable=False),
        sa.Column("frequency_text", sa.String(160), nullable=False),
        sa.Column("duration_days", sa.Integer()),
        sa.Column("quantity_prescribed", sa.Numeric(12, 3), nullable=False),
        sa.Column("quantity_unit", sa.String(40), nullable=False),
        sa.Column("refills", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indication", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_pharmacy_review"),
        sa.Column("quantity_dispensed_total", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("ordered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("cancelled_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_reason", sa.Text()),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_medication_order_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_medication_order_encounter_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "ordering_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_medication_order_ordering_department",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "pharmacy_department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_medication_order_pharmacy_department",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "medication_definition_id"],
            ["medication_definitions.hospital_id", "medication_definitions.id"],
            name="fk_medication_order_definition",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_medication_order_hospital_id"),
        sa.CheckConstraint(
            "status IN ('pending_pharmacy_review', 'approved_for_dispense', 'on_hold', "
            "'rejected', 'partially_dispensed', 'dispensed', 'cancelled')",
            name="ck_medication_order_status",
        ),
        sa.CheckConstraint(
            "route IN ('oral', 'topical', 'inhalation', 'intravenous', 'intramuscular', "
            "'subcutaneous', 'rectal', 'ophthalmic', 'otic', 'nasal', 'transdermal', 'other')",
            name="ck_medication_order_route",
        ),
        sa.CheckConstraint("quantity_prescribed > 0", name="ck_medication_order_quantity"),
        sa.CheckConstraint("duration_days IS NULL OR duration_days BETWEEN 1 AND 3650", name="ck_medication_order_duration"),
        sa.CheckConstraint("refills BETWEEN 0 AND 12", name="ck_medication_order_refills"),
        sa.CheckConstraint(
            "quantity_dispensed_total >= 0 AND quantity_dispensed_total <= quantity_prescribed",
            name="ck_medication_order_dispensed_quantity",
        ),
        sa.CheckConstraint(
            "(status IN ('partially_dispensed', 'dispensed') AND quantity_dispensed_total > 0) OR "
            "(status NOT IN ('partially_dispensed', 'dispensed') AND quantity_dispensed_total = 0)",
            name="ck_medication_order_dispense_state",
        ),
        sa.CheckConstraint(
            "status != 'dispensed' OR quantity_dispensed_total = quantity_prescribed",
            name="ck_medication_order_fully_dispensed",
        ),
        sa.CheckConstraint(
            "status != 'partially_dispensed' OR quantity_dispensed_total < quantity_prescribed",
            name="ck_medication_order_partial_dispense",
        ),
        sa.CheckConstraint(
            "status != 'cancelled' OR (cancelled_at IS NOT NULL AND cancelled_by_user_id IS NOT NULL "
            "AND cancellation_reason IS NOT NULL AND length(trim(cancellation_reason)) >= 3)",
            name="ck_medication_order_cancellation",
        ),
        sa.CheckConstraint(
            "status = 'cancelled' OR (cancelled_at IS NULL AND cancelled_by_user_id IS NULL AND cancellation_reason IS NULL)",
            name="ck_medication_order_no_unexpected_cancellation",
        ),
        sa.CheckConstraint(
            "length(trim(dose_text)) >= 1 AND length(trim(frequency_text)) >= 1 "
            "AND length(trim(quantity_unit)) >= 1 AND length(trim(indication)) >= 3",
            name="ck_medication_order_prescription_text",
        ),
    )
    op.create_index(
        "ix_medication_order_patient_encounter",
        "medication_orders",
        ["hospital_id", "patient_id", "encounter_id"],
    )
    op.create_index(
        "ix_medication_order_pharmacy_queue",
        "medication_orders",
        ["hospital_id", "pharmacy_department_id", "status", "ordered_at"],
    )

    op.create_table(
        "medication_order_review_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "order_id"],
            ["medication_orders.hospital_id", "medication_orders.id"],
            name="fk_medication_review_order",
        ),
        sa.CheckConstraint("decision IN ('approved', 'on_hold', 'rejected')", name="ck_medication_review_decision"),
        sa.CheckConstraint("length(trim(review_note)) >= 3", name="ck_medication_review_note"),
    )
    op.create_index(
        "ix_medication_review_order_time",
        "medication_order_review_events",
        ["hospital_id", "order_id", "reviewed_at"],
    )

    op.create_table(
        "medication_dispenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("dispensed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quantity_dispensed", sa.Numeric(12, 3), nullable=False),
        sa.Column("quantity_unit", sa.String(40), nullable=False),
        sa.Column("batch_reference", sa.String(120)),
        sa.Column("dispense_note", sa.Text()),
        sa.Column("dispensed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "order_id"],
            ["medication_orders.hospital_id", "medication_orders.id"],
            name="fk_medication_dispense_order",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_medication_dispense_hospital_id"),
        sa.CheckConstraint("quantity_dispensed > 0", name="ck_medication_dispense_quantity"),
        sa.CheckConstraint("length(trim(quantity_unit)) >= 1", name="ck_medication_dispense_unit"),
    )
    op.create_index(
        "ix_medication_dispense_order_time",
        "medication_dispenses",
        ["hospital_id", "order_id", "dispensed_at"],
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
    op.drop_index("ix_medication_dispense_order_time", table_name="medication_dispenses")
    op.drop_table("medication_dispenses")
    op.drop_index("ix_medication_review_order_time", table_name="medication_order_review_events")
    op.drop_table("medication_order_review_events")
    op.drop_index("ix_medication_order_pharmacy_queue", table_name="medication_orders")
    op.drop_index("ix_medication_order_patient_encounter", table_name="medication_orders")
    op.drop_table("medication_orders")
    op.drop_index("ix_medication_definition_department_status", table_name="medication_definitions")
    op.drop_table("medication_definitions")
