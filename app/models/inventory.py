import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_inventory_item_hospital_id"),
        UniqueConstraint("hospital_id", "item_code", name="uq_inventory_item_code"),
        CheckConstraint("item_type IN ('consumable', 'equipment', 'asset')", name="ck_inventory_item_type"),
        CheckConstraint("tracking_mode IN ('quantity', 'lot', 'serial')", name="ck_inventory_item_tracking"),
        CheckConstraint("status IN ('active', 'inactive', 'retired')", name="ck_inventory_item_status"),
        CheckConstraint("reorder_level >= 0", name="ck_inventory_item_reorder_level"),
        Index("ix_inventory_item_category", "hospital_id", "category", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    item_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    item_type: Mapped[str] = mapped_column(String(24), nullable=False)
    tracking_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="quantity")
    unit_of_measure: Mapped[str] = mapped_column(String(40), nullable=False)
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InventoryWarehouse(Base):
    __tablename__ = "inventory_warehouses"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_inventory_warehouse_hospital_id"),
        UniqueConstraint("hospital_id", "warehouse_code", name="uq_inventory_warehouse_code"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_inventory_warehouse_status"),
        Index("ix_inventory_warehouse_status", "hospital_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    warehouse_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    location_description: Mapped[str | None] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "purchase_order_id"], ["purchase_orders.hospital_id", "purchase_orders.id"], name="fk_goods_receipt_purchase_order"),
        UniqueConstraint("hospital_id", "id", "purchase_order_id", name="uq_goods_receipt_hospital_order"),
        ForeignKeyConstraint(["hospital_id", "warehouse_id"], ["inventory_warehouses.hospital_id", "inventory_warehouses.id"], name="fk_goods_receipt_warehouse"),
        UniqueConstraint("hospital_id", "id", name="uq_goods_receipt_hospital_id"),
        UniqueConstraint("hospital_id", "receipt_number", name="uq_goods_receipt_number"),
        CheckConstraint("status IN ('draft', 'posted', 'cancelled')", name="ck_goods_receipt_status"),
        CheckConstraint("(status = 'draft' AND posted_by_user_id IS NULL AND posted_at IS NULL) OR (status = 'posted' AND posted_by_user_id IS NOT NULL AND posted_at IS NOT NULL) OR status = 'cancelled'", name="ck_goods_receipt_post_state"),
        Index("ix_goods_receipt_queue", "hospital_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    receipt_number: Mapped[str] = mapped_column(String(80), nullable=False)
    delivery_note_reference: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    received_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    posted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "goods_receipt_id", "purchase_order_id"], ["goods_receipts.hospital_id", "goods_receipts.id", "goods_receipts.purchase_order_id"], name="fk_goods_receipt_line_receipt_order"),
        ForeignKeyConstraint(["hospital_id", "purchase_order_id", "purchase_order_line_id"], ["purchase_order_lines.hospital_id", "purchase_order_lines.purchase_order_id", "purchase_order_lines.id"], name="fk_goods_receipt_line_po_line"),
        ForeignKeyConstraint(["hospital_id", "inventory_item_id"], ["inventory_items.hospital_id", "inventory_items.id"], name="fk_goods_receipt_line_item"),
        UniqueConstraint("hospital_id", "id", name="uq_goods_receipt_line_hospital_id"),
        CheckConstraint("quantity_received > 0", name="ck_goods_receipt_line_quantity"),
        CheckConstraint("unit_cost >= 0", name="ck_goods_receipt_line_unit_cost"),
        Index("ix_goods_receipt_line_parent", "hospital_id", "goods_receipt_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    purchase_order_line_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    batch_number: Mapped[str | None] = mapped_column(String(120))
    serial_number: Mapped[str | None] = mapped_column(String(160))
    expiry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InventoryStockBalance(Base):
    __tablename__ = "inventory_stock_balances"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "warehouse_id"], ["inventory_warehouses.hospital_id", "inventory_warehouses.id"], name="fk_inventory_balance_warehouse"),
        ForeignKeyConstraint(["hospital_id", "inventory_item_id"], ["inventory_items.hospital_id", "inventory_items.id"], name="fk_inventory_balance_item"),
        UniqueConstraint("hospital_id", "warehouse_id", "inventory_item_id", name="uq_inventory_stock_balance"),
        CheckConstraint("quantity_on_hand >= 0 AND quantity_reserved >= 0 AND quantity_reserved <= quantity_on_hand", name="ck_inventory_stock_balance_quantity"),
        Index("ix_inventory_stock_item", "hospital_id", "inventory_item_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))
    quantity_reserved: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "warehouse_id"], ["inventory_warehouses.hospital_id", "inventory_warehouses.id"], name="fk_inventory_movement_warehouse"),
        ForeignKeyConstraint(["hospital_id", "inventory_item_id"], ["inventory_items.hospital_id", "inventory_items.id"], name="fk_inventory_movement_item"),
        UniqueConstraint("hospital_id", "id", name="uq_inventory_movement_hospital_id"),
        CheckConstraint("movement_type IN ('receipt', 'issue', 'transfer_in', 'transfer_out', 'adjustment', 'return')", name="ck_inventory_movement_type"),
        CheckConstraint("quantity > 0", name="ck_inventory_movement_quantity"),
        Index("ix_inventory_movement_ledger", "hospital_id", "inventory_item_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AssetRecord(Base):
    __tablename__ = "asset_records"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "inventory_item_id"], ["inventory_items.hospital_id", "inventory_items.id"], name="fk_asset_record_item"),
        ForeignKeyConstraint(["hospital_id", "warehouse_id"], ["inventory_warehouses.hospital_id", "inventory_warehouses.id"], name="fk_asset_record_warehouse"),
        UniqueConstraint("hospital_id", "id", name="uq_asset_record_hospital_id"),
        UniqueConstraint("hospital_id", "asset_tag", name="uq_asset_record_tag"),
        CheckConstraint("status IN ('in_service', 'under_maintenance', 'retired', 'disposed')", name="ck_asset_record_status"),
        Index("ix_asset_record_status", "hospital_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    asset_tag: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(160))
    manufacturer: Mapped[str | None] = mapped_column(String(160))
    model_number: Mapped[str | None] = mapped_column(String(120))
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    warranty_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="in_service")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
