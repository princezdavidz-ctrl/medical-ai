import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_employee_profile_hospital_id"),
        UniqueConstraint("hospital_id", "user_id", name="uq_employee_profile_user"),
        UniqueConstraint("hospital_id", "id", "user_id", name="uq_employee_profile_hospital_employee_user"),
        UniqueConstraint("hospital_id", "employee_number", name="uq_employee_profile_number"),
        ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_employee_profile_department"),
        CheckConstraint("employment_status IN ('active', 'on_leave', 'suspended', 'terminated')", name="ck_employee_profile_status"),
        CheckConstraint("employment_type IN ('permanent', 'contract', 'locum', 'intern', 'volunteer', 'other')", name="ck_employee_profile_type"),
        Index("ix_employee_profile_department_status", "hospital_id", "department_id", "employment_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    employee_number: Mapped[str] = mapped_column(String(80), nullable=False)
    job_title: Mapped[str] = mapped_column(String(160), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(24), nullable=False)
    employment_status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manager_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StaffCredential(Base):
    __tablename__ = "staff_credentials"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "employee_profile_id"], ["employee_profiles.hospital_id", "employee_profiles.id"], name="fk_staff_credential_employee"),
        UniqueConstraint("hospital_id", "id", name="uq_staff_credential_hospital_id"),
        CheckConstraint("verification_status IN ('reported', 'verified', 'rejected', 'expired')", name="ck_staff_credential_status"),
        CheckConstraint("valid_until IS NULL OR valid_until >= valid_from", name="ck_staff_credential_dates"),
        CheckConstraint("(verification_status = 'verified' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL) OR verification_status != 'verified'", name="ck_staff_credential_verification"),
        Index("ix_staff_credential_employee", "hospital_id", "employee_profile_id", "verification_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    employee_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(100), nullable=False)
    credential_number: Mapped[str] = mapped_column(String(160), nullable=False)
    issuing_body: Mapped[str] = mapped_column(String(180), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="reported")
    evidence_reference: Mapped[str | None] = mapped_column(String(160))
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StaffLeaveRequest(Base):
    __tablename__ = "staff_leave_requests"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "employee_profile_id"], ["employee_profiles.hospital_id", "employee_profiles.id"], name="fk_staff_leave_employee"),
        UniqueConstraint("hospital_id", "id", name="uq_staff_leave_hospital_id"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name="ck_staff_leave_status"),
        CheckConstraint("end_at > start_at", name="ck_staff_leave_dates"),
        CheckConstraint("(status = 'pending' AND decided_by_user_id IS NULL AND decided_at IS NULL AND decision_note IS NULL) OR (status IN ('approved', 'rejected') AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL) OR status = 'cancelled'", name="ck_staff_leave_decision"),
        CheckConstraint("(status = 'pending' AND decided_by_user_id IS NULL AND decided_at IS NULL AND decision_note IS NULL) OR (status IN ('approved', 'rejected') AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL) OR (status = 'cancelled')", name="ck_staff_leave_decision"),
        Index("ix_staff_leave_queue", "hospital_id", "status", "start_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    employee_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    leave_type: Mapped[str] = mapped_column(String(40), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
