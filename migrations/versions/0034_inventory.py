"""Create tenant-isolated inventory, goods receipt, stock ledger and asset register."""
from alembic import op
import sqlalchemy as sa

revision = "0034_inventory"
down_revision = "0033_procurement"
branch_labels = None
depends_on = None

TABLES = ("inventory_items", "inventory_warehouses", "goods_receipts", "goods_receipt_lines", "inventory_stock_balances", "inventory_movements", "asset_records")


def upgrade() -> None:
    op.create_unique_constraint("uq_purchase_order_line_hospital_order_id", "purchase_order_lines", ["hospital_id", "purchase_order_id", "id"])
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("item_code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("item_type", sa.String(24), nullable=False),
        sa.Column("tracking_mode", sa.String(24), nullable=False, server_default="quantity"),
        sa.Column("unit_of_measure", sa.String(40), nullable=False),
        sa.Column("reorder_level", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "id", name="uq_inventory_item_hospital_id"),
        sa.UniqueConstraint("hospital_id", "item_code", name="uq_inventory_item_code"),
        sa.CheckConstraint("item_type IN ('consumable', 'equipment', 'asset')", name="ck_inventory_item_type"),
        sa.CheckConstraint("tracking_mode IN ('quantity', 'lot', 'serial')", name="ck_inventory_item_tracking"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'retired')", name="ck_inventory_item_status"),
        sa.CheckConstraint("reorder_level >= 0", name="ck_inventory_item_reorder_level"),
    )
    op.create_index("ix_inventory_item_category", "inventory_items", ["hospital_id", "category", "status"])
    op.create_table(
        "inventory_warehouses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("warehouse_code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("location_description", sa.String(240)),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "id", name="uq_inventory_warehouse_hospital_id"),
        sa.UniqueConstraint("hospital_id", "warehouse_code", name="uq_inventory_warehouse_code"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_inventory_warehouse_status"),
    )
    op.create_index("ix_inventory_warehouse_status", "inventory_warehouses", ["hospital_id", "status"])
    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_number", sa.String(80), nullable=False),
        sa.Column("delivery_note_reference", sa.String(160)),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("received_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("posted_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "purchase_order_id"], ["purchase_orders.hospital_id", "purchase_orders.id"], name="fk_goods_receipt_purchase_order"),
        sa.ForeignKeyConstraint(["hospital_id", "warehouse_id"], ["inventory_warehouses.hospital_id", "inventory_warehouses.id"], name="fk_goods_receipt_warehouse"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_goods_receipt_hospital_id"),
        sa.UniqueConstraint("hospital_id", "id", "purchase_order_id", name="uq_goods_receipt_hospital_order"),
        sa.UniqueConstraint("hospital_id", "receipt_number", name="uq_goods_receipt_number"),
        sa.CheckConstraint("status IN ('draft', 'posted', 'cancelled')", name="ck_goods_receipt_status"),
        sa.CheckConstraint("(status = 'draft' AND posted_by_user_id IS NULL AND posted_at IS NULL) OR (status = 'posted' AND posted_by_user_id IS NOT NULL AND posted_at IS NOT NULL) OR status = 'cancelled'", name="ck_goods_receipt_post_state"),
    )
    op.create_index("ix_goods_receipt_queue", "goods_receipts", ["hospital_id", "status", "created_at"])
    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("goods_receipt_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_order_line_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_received", sa.Numeric(14, 3), nullable=False),
        sa.Column("batch_number", sa.String(120)),
        sa.Column("serial_number", sa.String(160)),
        sa.Column("expiry_at", sa.DateTime(timezone=True)),
        sa.Column("unit_cost", sa.Numeric(16, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "goods_receipt_id", "purchase_order_id"], ["goods_receipts.hospital_id", "goods_receipts.id", "goods_receipts.purchase_order_id"], name="fk_goods_receipt_line_receipt_order"),
        sa.ForeignKeyConstraint(["hospital_id", "purchase_order_id", "purchase_order_line_id"], ["purchase_order_lines.hospital_id", "purchase_order_lines.purchase_order_id", "purchase_order_lines.id"], name="fk_goods_receipt_line_po_line"),
        sa.ForeignKeyConstraint(["hospital_id", "inventory_item_id"], ["inventory_items.hospital_id", "inventory_items.id"], name="fk_goods_receipt_line_item"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_goods_receipt_line_hospital_id"),
        sa.CheckConstraint("quantity_received > 0", name="ck_goods_receipt_line_quantity"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_goods_receipt_line_unit_cost"),
    )
    op.create_index("ix_goods_receipt_line_parent", "goods_receipt_lines", ["hospital_id", "goods_receipt_id"])
    op.create_table(
        "inventory_stock_balances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_on_hand", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("quantity_reserved", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "warehouse_id"], ["inventory_warehouses.hospital_id", "inventory_warehouses.id"], name="fk_inventory_balance_warehouse"),
        sa.ForeignKeyConstraint(["hospital_id", "inventory_item_id"], ["inventory_items.hospital_id", "inventory_items.id"], name="fk_inventory_balance_item"),
        sa.UniqueConstraint("hospital_id", "warehouse_id", "inventory_item_id", name="uq_inventory_stock_balance"),
        sa.CheckConstraint("quantity_on_hand >= 0 AND quantity_reserved >= 0 AND quantity_reserved <= quantity_on_hand", name="ck_inventory_stock_balance_quantity"),
    )
    op.create_index("ix_inventory_stock_item", "inventory_stock_balances", ["hospital_id", "inventory_item_id"])
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.String(24), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("reference_type", sa.String(40), nullable=False),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "warehouse_id"], ["inventory_warehouses.hospital_id", "inventory_warehouses.id"], name="fk_inventory_movement_warehouse"),
        sa.ForeignKeyConstraint(["hospital_id", "inventory_item_id"], ["inventory_items.hospital_id", "inventory_items.id"], name="fk_inventory_movement_item"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_inventory_movement_hospital_id"),
        sa.CheckConstraint("movement_type IN ('receipt', 'issue', 'transfer_in', 'transfer_out', 'adjustment', 'return')", name="ck_inventory_movement_type"),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_movement_quantity"),
    )
    op.create_index("ix_inventory_movement_ledger", "inventory_movements", ["hospital_id", "inventory_item_id", "created_at"])
    op.create_table(
        "asset_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("asset_tag", sa.String(100), nullable=False),
        sa.Column("serial_number", sa.String(160)),
        sa.Column("manufacturer", sa.String(160)),
        sa.Column("model_number", sa.String(120)),
        sa.Column("acquired_at", sa.DateTime(timezone=True)),
        sa.Column("warranty_until", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False, server_default="in_service"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "inventory_item_id"], ["inventory_items.hospital_id", "inventory_items.id"], name="fk_asset_record_item"),
        sa.ForeignKeyConstraint(["hospital_id", "warehouse_id"], ["inventory_warehouses.hospital_id", "inventory_warehouses.id"], name="fk_asset_record_warehouse"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_asset_record_hospital_id"),
        sa.UniqueConstraint("hospital_id", "asset_tag", name="uq_asset_record_tag"),
        sa.CheckConstraint("status IN ('in_service', 'under_maintenance', 'retired', 'disposed')", name="ck_asset_record_status"),
    )
    op.create_index("ix_asset_record_status", "asset_records", ["hospital_id", "status"])
    op.create_index("uq_inventory_receipt_serial", "goods_receipt_lines", ["hospital_id", "serial_number"], unique=True, postgresql_where=sa.text("serial_number IS NOT NULL"))
    op.create_index("uq_asset_record_serial", "asset_records", ["hospital_id", "serial_number"], unique=True, postgresql_where=sa.text("serial_number IS NOT NULL"))
    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))
    op.execute("""
        CREATE FUNCTION prevent_inventory_movement_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'inventory movements are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_inventory_movements_immutable
        BEFORE UPDATE OR DELETE ON inventory_movements
        FOR EACH ROW EXECUTE FUNCTION prevent_inventory_movement_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_inventory_movements_immutable ON inventory_movements")
    op.execute("DROP FUNCTION IF EXISTS prevent_inventory_movement_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
    op.drop_constraint("uq_purchase_order_line_hospital_order_id", "purchase_order_lines", type_="unique")
