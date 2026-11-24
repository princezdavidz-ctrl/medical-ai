import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, String, Text, UniqueConstraint, Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Ward(Base):
    __tablename__ = "wards"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_ward_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_ward_hospital_id_id"),
        UniqueConstraint("hospital_id", "code", name="uq_ward_hospital_code"),
        CheckConstraint(
            "ward_type IN ('general', 'medical', 'surgical', 'maternity', 'pediatric', 'icu', 'other')",
            name="ck_ward_type",
        ),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_ward_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    ward_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HospitalBed(Base):
    __tablename__ = "hospital_beds"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "ward_id"],
            ["wards.hospital_id", "wards.id"],
            name="fk_hospital_bed_ward",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_hospital_bed_hospital_id_id"),
        UniqueConstraint("hospital_id", "ward_id", "bed_number", name="uq_hospital_bed_number"),
        CheckConstraint(
            "bed_type IN ('standard', 'isolation', 'high_dependency', 'critical_care', 'maternity', 'pediatric', 'other')",
            name="ck_hospital_bed_type",
        ),
        CheckConstraint(
            "status IN ('available', 'occupied', 'cleaning', 'maintenance', 'blocked')",
            name="ck_hospital_bed_status",
        ),
        Index("ix_hospital_beds_ward_status", "hospital_id", "ward_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    ward_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    bed_number: Mapped[str] = mapped_column(String(40), nullable=False)
    bed_type: Mapped[str] = mapped_column(String(24), nullable=False, default="standard")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="available")
    isolation_capable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(String(500))


class InpatientAdmission(Base):
    __tablename__ = "inpatient_admissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_inpatient_admission_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_inpatient_admission_encounter_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "source_encounter_id"],
            ["encounters.hospital_id", "encounters.id"],
            name="fk_inpatient_admission_source_encounter",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "ward_id"],
            ["wards.hospital_id", "wards.id"],
            name="fk_inpatient_admission_ward",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_inpatient_admission_hospital_id_id"),
        CheckConstraint(
            "status IN ('requested', 'accepted', 'admitted', 'discharged', 'cancelled')",
            name="ck_inpatient_admission_status",
        ),
        Index(
            "uq_inpatient_active_patient",
            "hospital_id", "patient_id",
            unique=True,
            postgresql_where=text("status IN ('requested', 'accepted', 'admitted')"),
        ),
        Index("ix_inpatient_admission_ward_status", "hospital_id", "ward_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_encounter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    ward_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    discharged_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    admission_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="requested")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discharge_summary: Mapped[str | None] = mapped_column(Text)


class BedAssignment(Base):
    __tablename__ = "bed_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "admission_id"],
            ["inpatient_admissions.hospital_id", "inpatient_admissions.id"],
            name="fk_bed_assignment_admission",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "bed_id"],
            ["hospital_beds.hospital_id", "hospital_beds.id"],
            name="fk_bed_assignment_bed",
        ),
        CheckConstraint("status IN ('active', 'released')", name="ck_bed_assignment_status"),
        CheckConstraint(
            "status != 'released' OR released_at IS NOT NULL",
            name="ck_bed_assignment_release_timestamp",
        ),
        Index(
            "uq_bed_assignment_active_bed",
            "hospital_id", "bed_id", unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_bed_assignment_active_admission",
            "hospital_id", "admission_id", unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    admission_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    bed_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
