import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, String, Text, UniqueConstraint, Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TheatreRoom(Base):
    __tablename__ = "theatre_rooms"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_theatre_room_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_theatre_room_hospital_id_id"),
        UniqueConstraint("hospital_id", "code", name="uq_theatre_room_hospital_code"),
        CheckConstraint(
            "theatre_type IN ('general', 'orthopedic', 'cardiac', 'obstetric', 'neurosurgical', 'other')",
            name="ck_theatre_room_type",
        ),
        CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name="ck_theatre_room_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    theatre_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SurgicalCase(Base):
    __tablename__ = "surgical_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_surgical_case_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_surgical_case_encounter_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "theatre_room_id"],
            ["theatre_rooms.hospital_id", "theatre_rooms.id"],
            name="fk_surgical_case_theatre",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_surgical_case_hospital_id_id"),
        CheckConstraint(
            "urgency IN ('elective', 'urgent', 'emergency')",
            name="ck_surgical_case_urgency",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'recovery', 'completed', 'cancelled')",
            name="ck_surgical_case_status",
        ),
        CheckConstraint("length(trim(planned_procedure)) >= 3", name="ck_surgical_case_procedure"),
        CheckConstraint("scheduled_end_at > scheduled_start_at", name="ck_surgical_case_schedule"),
        CheckConstraint(
            "status != 'cancelled' OR (cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL)",
            name="ck_surgical_case_cancelled_fields",
        ),
        Index("ix_surgical_case_theatre_schedule", "hospital_id", "theatre_room_id", "status", "scheduled_start_at"),
        Index("ix_surgical_case_encounter", "hospital_id", "encounter_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    theatre_room_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    surgeon_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    planned_procedure: Mapped[str] = mapped_column(String(2000), nullable=False)
    urgency: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="scheduled")
    scheduled_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SurgicalSafetyChecklist(Base):
    __tablename__ = "surgical_safety_checklists"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "surgical_case_id"],
            ["surgical_cases.hospital_id", "surgical_cases.id"],
            name="fk_surgical_checklist_case",
        ),
        UniqueConstraint("hospital_id", "surgical_case_id", "phase", "revision", name="uq_surgical_checklist_revision"),
        CheckConstraint("phase IN ('sign_in', 'time_out', 'sign_out')", name="ck_surgical_checklist_phase"),
        CheckConstraint("revision >= 1", name="ck_surgical_checklist_revision"),
        Index("ix_surgical_checklist_case", "hospital_id", "surgical_case_id", "phase", "revision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    surgical_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_identity_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    procedure_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    site_marking_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    site_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    counts_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    consent_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allergies_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    anesthesia_safety_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    equipment_ready: Mapped[bool] = mapped_column(Boolean, nullable=False)
    counts_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnesthesiaRecord(Base):
    __tablename__ = "anesthesia_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "surgical_case_id"],
            ["surgical_cases.hospital_id", "surgical_cases.id"],
            name="fk_anesthesia_record_case",
        ),
        UniqueConstraint("hospital_id", "surgical_case_id", name="uq_anesthesia_record_case"),
        CheckConstraint(
            "anesthesia_type IN ('general', 'regional', 'local', 'sedation', 'combined')",
            name="ck_anesthesia_record_type",
        ),
        CheckConstraint("asa_class BETWEEN 1 AND 5", name="ck_anesthesia_record_asa"),
        CheckConstraint("ended_at IS NULL OR ended_at > started_at", name="ck_anesthesia_record_time"),
        CheckConstraint("length(trim(pre_anesthesia_assessment)) >= 3", name="ck_anesthesia_assessment"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    surgical_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    anesthesia_provider_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    anesthesia_type: Mapped[str] = mapped_column(String(24), nullable=False)
    asa_class: Mapped[int] = mapped_column(Integer, nullable=False)
    airway_method: Mapped[str | None] = mapped_column(String(160))
    pre_anesthesia_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    intraoperative_notes: Mapped[str | None] = mapped_column(Text)
    complications: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SurgicalEvent(Base):
    __tablename__ = "surgical_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "surgical_case_id"],
            ["surgical_cases.hospital_id", "surgical_cases.id"],
            name="fk_surgical_event_case",
        ),
        CheckConstraint(
            "event_type IN ('incision', 'procedure_step', 'specimen', 'count_check', "
            "'closure', 'complication', 'handover', 'other')",
            name="ck_surgical_event_type",
        ),
        CheckConstraint("length(trim(description)) >= 3", name="ck_surgical_event_description"),
        Index("ix_surgical_event_case", "hospital_id", "surgical_case_id", "performed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    surgical_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    performed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SurgicalNote(Base):
    __tablename__ = "surgical_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "surgical_case_id"],
            ["surgical_cases.hospital_id", "surgical_cases.id"],
            name="fk_surgical_note_case",
        ),
        CheckConstraint(
            "note_type IN ('operative', 'post_op', 'handover', 'incident', 'other')",
            name="ck_surgical_note_type",
        ),
        CheckConstraint("length(trim(note_text)) >= 3", name="ck_surgical_note_text"),
        Index("ix_surgical_note_case", "hospital_id", "surgical_case_id", "signed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    surgical_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note_type: Mapped[str] = mapped_column(String(24), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
