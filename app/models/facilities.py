import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class FacilityLocation(Base):
    __tablename__ = "facility_locations"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_facility_location_hospital_id"),
        UniqueConstraint("hospital_id", "location_code", name="uq_facility_location_code"),
        ForeignKeyConstraint(["hospital_id", "parent_location_id"], ["facility_locations.hospital_id", "facility_locations.id"], name="fk_facility_location_parent"),
        CheckConstraint("status IN ('active', 'inactive', 'closed')", name="ck_facility_location_status"),
        CheckConstraint("location_type IN ('campus', 'building', 'floor', 'wing', 'department', 'room', 'utility_area', 'external_area')", name="ck_facility_location_type"),
        CheckConstraint("parent_location_id IS NULL OR parent_location_id != id", name="ck_facility_location_not_self_parent"),
        Index("ix_facility_location_parent", "hospital_id", "parent_location_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    parent_location_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    location_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    location_type: Mapped[str] = mapped_column(String(32), nullable=False)
    building: Mapped[str | None] = mapped_column(String(120))
    floor: Mapped[str | None] = mapped_column(String(40))
    room_number: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaintenanceWorkOrder(Base):
    __tablename__ = "maintenance_work_orders"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "facility_location_id"], ["facility_locations.hospital_id", "facility_locations.id"], name="fk_maintenance_order_location"),
        ForeignKeyConstraint(["hospital_id", "asset_record_id"], ["asset_records.hospital_id", "asset_records.id"], name="fk_maintenance_order_asset"),
        UniqueConstraint("hospital_id", "id", name="uq_maintenance_order_hospital_id"),
        UniqueConstraint("hospital_id", "work_order_number", name="uq_maintenance_order_number"),
        CheckConstraint("category IN ('electrical', 'plumbing', 'hvac', 'building', 'medical_equipment', 'safety', 'other')", name="ck_maintenance_order_category"),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_maintenance_order_priority"),
        CheckConstraint("status IN ('requested', 'approved', 'assigned', 'in_progress', 'completed', 'rejected', 'cancelled')", name="ck_maintenance_order_status"),
        CheckConstraint("(status IN ('requested', 'rejected', 'cancelled') AND approved_by_user_id IS NULL AND approved_at IS NULL) OR (status IN ('approved', 'assigned', 'in_progress', 'completed') AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL)", name="ck_maintenance_order_approval_state"),
        CheckConstraint("(status IN ('completed') AND completed_by_user_id IS NOT NULL AND completed_at IS NOT NULL) OR (status != 'completed' AND completed_by_user_id IS NULL AND completed_at IS NULL)", name="ck_maintenance_order_completion_state"),
        Index("ix_maintenance_order_queue", "hospital_id", "status", "priority", "created_at"),
        Index("ix_maintenance_order_asset", "hospital_id", "asset_record_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    work_order_number: Mapped[str] = mapped_column(String(80), nullable=False)
    facility_location_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    asset_record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(24), nullable=False, default="normal")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="requested")
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaintenanceEvent(Base):
    __tablename__ = "maintenance_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "work_order_id"], ["maintenance_work_orders.hospital_id", "maintenance_work_orders.id"], name="fk_maintenance_event_order"),
        UniqueConstraint("hospital_id", "id", name="uq_maintenance_event_hospital_id"),
        Index("ix_maintenance_event_order_time", "hospital_id", "work_order_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    work_order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
