import uuid
from datetime import datetime, time
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, Time, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class StaffShiftTemplate(Base):
    __tablename__ = "staff_shift_templates"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_shift_template_department"),
        UniqueConstraint("hospital_id", "id", name="uq_shift_template_hospital_id"),
        UniqueConstraint("hospital_id", "code", name="uq_shift_template_code"),
        CheckConstraint("category IN ('day', 'evening', 'night', 'on_call', 'other')", name="ck_shift_template_category"),
        CheckConstraint("start_time != end_time", name="ck_shift_template_time_range"),
        CheckConstraint("break_minutes BETWEEN 0 AND 240", name="ck_shift_template_break_minutes"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_shift_template_status"),
        Index("ix_shift_template_department", "hospital_id", "department_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StaffShiftAssignment(Base):
    __tablename__ = "staff_shift_assignments"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "employee_profile_id", "staff_user_id"], ["employee_profiles.hospital_id", "employee_profiles.id", "employee_profiles.user_id"], name="fk_staff_shift_employee_user"),
        ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_staff_shift_department"),
        ForeignKeyConstraint(["hospital_id", "shift_template_id"], ["staff_shift_templates.hospital_id", "staff_shift_templates.id"], name="fk_staff_shift_template"),
        UniqueConstraint("hospital_id", "id", name="uq_staff_shift_hospital_id"),
        UniqueConstraint("hospital_id", "id", "staff_user_id", name="uq_staff_shift_hospital_user"),
        CheckConstraint("status IN ('scheduled', 'confirmed', 'completed', 'cancelled')", name="ck_staff_shift_status"),
        CheckConstraint("ends_at > starts_at", name="ck_staff_shift_time_range"),
        CheckConstraint("ends_at <= starts_at + interval '24 hours'", name="ck_staff_shift_max_duration"),
        Index("ix_staff_shift_staff_time", "hospital_id", "staff_user_id", "starts_at", "ends_at"),
        Index("ix_staff_shift_department_time", "hospital_id", "department_id", "starts_at"),
        Index("ix_staff_shift_template_time", "hospital_id", "shift_template_id", "starts_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    employee_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    staff_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    shift_template_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="scheduled")
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class StaffShiftSwapRequest(Base):
    __tablename__ = "staff_shift_swap_requests"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "shift_assignment_id"], ["staff_shift_assignments.hospital_id", "staff_shift_assignments.id"], name="fk_shift_swap_assignment"),
        UniqueConstraint("hospital_id", "id", name="uq_shift_swap_hospital_id"),
        CheckConstraint("status IN ('pending_target', 'accepted', 'declined', 'approved', 'rejected', 'cancelled')", name="ck_shift_swap_status"),
        CheckConstraint("requester_user_id != target_user_id", name="ck_shift_swap_not_self"),
        CheckConstraint("(status = 'pending_target' AND responded_by_user_id IS NULL AND responded_at IS NULL AND decided_by_user_id IS NULL AND decided_at IS NULL) OR (status IN ('accepted', 'declined') AND responded_by_user_id = target_user_id AND responded_at IS NOT NULL AND decided_by_user_id IS NULL AND decided_at IS NULL) OR (status IN ('approved', 'rejected') AND responded_by_user_id = target_user_id AND responded_at IS NOT NULL AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL) OR status = 'cancelled'", name="ck_shift_swap_decision_state"),
        Index("ix_shift_swap_target_queue", "hospital_id", "target_user_id", "status", "created_at"),
        Index("ix_shift_swap_shift", "hospital_id", "shift_assignment_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    shift_assignment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requester_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_target")
    responded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StaffShiftAttendance(Base):
    __tablename__ = "staff_shift_attendance"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "shift_assignment_id", "staff_user_id"], ["staff_shift_assignments.hospital_id", "staff_shift_assignments.id", "staff_shift_assignments.staff_user_id"], name="fk_shift_attendance_assignment_staff"),
        UniqueConstraint("hospital_id", "id", name="uq_shift_attendance_hospital_id"),
        UniqueConstraint("hospital_id", "shift_assignment_id", name="uq_shift_attendance_per_shift"),
        CheckConstraint("status IN ('open', 'submitted', 'approved', 'rejected')", name="ck_shift_attendance_status"),
        CheckConstraint("check_out_at IS NULL OR check_out_at > check_in_at", name="ck_shift_attendance_time_range"),
        CheckConstraint("(status = 'open' AND check_out_at IS NULL AND decided_by_user_id IS NULL AND decided_at IS NULL) OR (status = 'submitted' AND check_out_at IS NOT NULL AND decided_by_user_id IS NULL AND decided_at IS NULL) OR (status IN ('approved', 'rejected') AND check_out_at IS NOT NULL AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL)", name="ck_shift_attendance_decision_state"),
        CheckConstraint("source = 'manual'", name="ck_shift_attendance_manual_source"),
        Index("ix_shift_attendance_review", "hospital_id", "status", "check_in_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    shift_assignment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    staff_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    note: Mapped[str | None] = mapped_column(String(1000))
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StaffScheduleEvent(Base):
    __tablename__ = "staff_schedule_events"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_staff_schedule_event_hospital_id"),
        CheckConstraint("event_type IN ('shift_template_created', 'shift_template_updated', 'shift_assigned', 'shift_updated', 'shift_cancelled', 'swap_requested', 'swap_accepted', 'swap_approved', 'swap_rejected', 'swap_cancelled', 'attendance_checked_in', 'attendance_checked_out', 'attendance_approved', 'attendance_rejected')", name="ck_staff_schedule_event_type"),
        Index("ix_staff_schedule_event_history", "hospital_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
