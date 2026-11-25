"""Create tenant-isolated procurement and purchase-order workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0033_procurement"
down_revision = "0032_hr"
branch_labels = None
depends_on = None

TABLES = (
    "procurement_vendors",
    "purchase_requisitions",
    "purchase_requisition_lines",
    "purchase_orders",
    "purchase_order_lines",
    "procurement_events",
)


def upgrade() -> None:
    op.create_table(
        "procurement_vendors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("vendor_code", sa.String(80), nullable=False),
        sa.Column("legal_name", sa.String(240), nullable=False),
        sa.Column("vendor_type", sa.String(24), nullable=False),
        sa.Column("registration_number", sa.String(120)),
        sa.Column("tax_pin_reference", sa.String(120)),
        sa.Column("contact_name", sa.String(180)),
        sa.Column("contact_email", sa.String(320)),
        sa.Column("contact_phone", sa.String(40)),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "id", name="uq_procurement_vendor_hospital_id"),
        sa.UniqueConstraint("hospital_id", "vendor_code", name="uq_procurement_vendor_code"),
        sa.CheckConstraint("status IN ('draft', 'active', 'suspended', 'retired')", name="ck_procurement_vendor_status"),
        sa.CheckConstraint("vendor_type IN ('company', 'individual', 'nonprofit', 'government', 'other')", name="ck_procurement_vendor_type"),
        sa.CheckConstraint("approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id", name="ck_procurement_vendor_independent_approval"),
    )
    op.create_index("ix_procurement_vendor_status", "procurement_vendors", ["hospital_id", "status"])

    op.create_table(
        "purchase_requisitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("requisition_number", sa.String(80), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("required_by", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_purchase_requisition_department"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_purchase_requisition_hospital_id"),
        sa.UniqueConstraint("hospital_id", "requisition_number", name="uq_purchase_requisition_number"),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'converted', 'cancelled')", name="ck_purchase_requisition_status"),
        sa.CheckConstraint("approved_by_user_id IS NULL OR approved_by_user_id != requested_by_user_id", name="ck_purchase_requisition_independent_approval"),
    )
    op.create_index("ix_purchase_requisition_queue", "purchase_requisitions", ["hospital_id", "status", "created_at"])
    op.create_index("ix_purchase_requisition_department", "purchase_requisitions", ["hospital_id", "department_id", "status"])

    op.create_table(
        "purchase_requisition_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("requisition_id", sa.Uuid(), nullable=False),
        sa.Column("item_description", sa.String(240), nullable=False),
        sa.Column("specification", sa.Text()),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_of_measure", sa.String(40), nullable=False),
        sa.Column("estimated_unit_cost", sa.Numeric(16, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "requisition_id"], ["purchase_requisitions.hospital_id", "purchase_requisitions.id"], name="fk_purchase_requisition_line_parent"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_purchase_requisition_line_hospital_id"),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_requisition_line_quantity"),
    )
    op.create_index("ix_purchase_requisition_line_parent", "purchase_requisition_lines", ["hospital_id", "requisition_id"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("requisition_id", sa.Uuid(), nullable=False),
        sa.Column("order_number", sa.String(80), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("issued_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "vendor_id"], ["procurement_vendors.hospital_id", "procurement_vendors.id"], name="fk_purchase_order_vendor"),
        sa.ForeignKeyConstraint(["hospital_id", "requisition_id"], ["purchase_requisitions.hospital_id", "purchase_requisitions.id"], name="fk_purchase_order_requisition"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_purchase_order_hospital_id"),
        sa.UniqueConstraint("hospital_id", "order_number", name="uq_purchase_order_number"),
        sa.UniqueConstraint("hospital_id", "requisition_id", name="uq_purchase_order_requisition"),
        sa.CheckConstraint("status IN ('draft', 'issued', 'partially_received', 'received', 'cancelled')", name="ck_purchase_order_status"),
        sa.CheckConstraint("total_amount >= 0 AND currency ~ '^[A-Z]{3}$'", name="ck_purchase_order_amount_currency"),
    )
    op.create_index("ix_purchase_order_queue", "purchase_orders", ["hospital_id", "status", "created_at"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("requisition_line_id", sa.Uuid(), nullable=False),
        sa.Column("item_description", sa.String(240), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_of_measure", sa.String(40), nullable=False),
        sa.Column("unit_price", sa.Numeric(16, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(16, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "purchase_order_id"], ["purchase_orders.hospital_id", "purchase_orders.id"], name="fk_purchase_order_line_parent"),
        sa.ForeignKeyConstraint(["hospital_id", "requisition_line_id"], ["purchase_requisition_lines.hospital_id", "purchase_requisition_lines.id"], name="fk_purchase_order_line_requisition"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_purchase_order_line_hospital_id"),
        sa.UniqueConstraint("hospital_id", "requisition_line_id", name="uq_purchase_order_line_requisition_line"),
        sa.CheckConstraint("quantity > 0 AND unit_price >= 0 AND line_total >= 0", name="ck_purchase_order_line_amounts"),
    )
    op.create_index("ix_purchase_order_line_parent", "purchase_order_lines", ["hospital_id", "purchase_order_id"])

    op.create_table(
        "procurement_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_procurement_event_time", "procurement_events", ["hospital_id", "resource_type", "resource_id", "created_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(
            f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" '
            "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
            "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
        ))
    op.execute("""
        CREATE FUNCTION prevent_procurement_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'procurement events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_procurement_events_immutable
        BEFORE UPDATE OR DELETE ON procurement_events
        FOR EACH ROW EXECUTE FUNCTION prevent_procurement_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_procurement_events_immutable ON procurement_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_procurement_event_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
