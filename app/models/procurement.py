import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcurementVendor(Base):
    __tablename__ = "procurement_vendors"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_procurement_vendor_hospital_id"),
        UniqueConstraint("hospital_id", "vendor_code", name="uq_procurement_vendor_code"),
        CheckConstraint("status IN ('draft', 'active', 'suspended', 'retired')", name="ck_procurement_vendor_status"),
        CheckConstraint("vendor_type IN ('company', 'individual', 'nonprofit', 'government', 'other')", name="ck_procurement_vendor_type"),
        CheckConstraint("approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id", name="ck_procurement_vendor_independent_approval"),
        Index("ix_procurement_vendor_status", "hospital_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    vendor_code: Mapped[str] = mapped_column(String(80), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    vendor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(120))
    tax_pin_reference: Mapped[str | None] = mapped_column(String(120))
    contact_name: Mapped[str | None] = mapped_column(String(180))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PurchaseRequisition(Base):
    __tablename__ = "purchase_requisitions"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_purchase_requisition_department"),
        UniqueConstraint("hospital_id", "id", name="uq_purchase_requisition_hospital_id"),
        UniqueConstraint("hospital_id", "requisition_number", name="uq_purchase_requisition_number"),
        CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'converted', 'cancelled')", name="ck_purchase_requisition_status"),
        CheckConstraint("required_by IS NULL OR required_by >= created_at", name="ck_purchase_requisition_required_date"),
        CheckConstraint("approved_by_user_id IS NULL OR approved_by_user_id != requested_by_user_id", name="ck_purchase_requisition_independent_approval"),
        Index("ix_purchase_requisition_queue", "hospital_id", "status", "created_at"),
        Index("ix_purchase_requisition_department", "hospital_id", "department_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requisition_number: Mapped[str] = mapped_column(String(80), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    required_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PurchaseRequisitionLine(Base):
    __tablename__ = "purchase_requisition_lines"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "requisition_id"], ["purchase_requisitions.hospital_id", "purchase_requisitions.id"], name="fk_purchase_requisition_line_parent"),
        UniqueConstraint("hospital_id", "id", name="uq_purchase_requisition_line_hospital_id"),
        CheckConstraint("quantity > 0", name="ck_purchase_requisition_line_quantity"),
        Index("ix_purchase_requisition_line_parent", "hospital_id", "requisition_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    requisition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    item_description: Mapped[str] = mapped_column(String(240), nullable=False)
    specification: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(40), nullable=False)
    estimated_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "vendor_id"], ["procurement_vendors.hospital_id", "procurement_vendors.id"], name="fk_purchase_order_vendor"),
        ForeignKeyConstraint(["hospital_id", "requisition_id"], ["purchase_requisitions.hospital_id", "purchase_requisitions.id"], name="fk_purchase_order_requisition"),
        UniqueConstraint("hospital_id", "id", name="uq_purchase_order_hospital_id"),
        UniqueConstraint("hospital_id", "order_number", name="uq_purchase_order_number"),
        UniqueConstraint("hospital_id", "requisition_id", name="uq_purchase_order_requisition"),
        CheckConstraint("status IN ('draft', 'issued', 'partially_received', 'received', 'cancelled')", name="ck_purchase_order_status"),
        CheckConstraint("total_amount >= 0 AND currency ~ '^[A-Z]{3}$'", name="ck_purchase_order_amount_currency"),
        Index("ix_purchase_order_queue", "hospital_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requisition_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    order_number: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    issued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "purchase_order_id"], ["purchase_orders.hospital_id", "purchase_orders.id"], name="fk_purchase_order_line_parent"),
        ForeignKeyConstraint(["hospital_id", "requisition_line_id"], ["purchase_requisition_lines.hospital_id", "purchase_requisition_lines.id"], name="fk_purchase_order_line_requisition"),
        UniqueConstraint("hospital_id", "id", name="uq_purchase_order_line_hospital_id"),
        UniqueConstraint("hospital_id", "requisition_line_id", name="uq_purchase_order_line_requisition_line"),
        CheckConstraint("quantity > 0 AND unit_price >= 0 AND line_total >= 0", name="ck_purchase_order_line_amounts"),
        Index("ix_purchase_order_line_parent", "hospital_id", "purchase_order_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requisition_line_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    item_description: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcurementEvent(Base):
    __tablename__ = "procurement_events"
    __table_args__ = (
        Index("ix_procurement_event_time", "hospital_id", "resource_type", "resource_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
