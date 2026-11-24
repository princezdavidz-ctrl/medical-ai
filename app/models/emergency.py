import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Integer, Numeric, String, Text, UniqueConstraint, Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmergencyVisit(Base):
    __tablename__ = "emergency_visits"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_emergency_visit_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_emergency_visit_encounter_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_emergency_visit_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_emergency_visit_hospital_id_id"),
        UniqueConstraint("hospital_id", "encounter_id", name="uq_emergency_visit_encounter"),
        CheckConstraint(
            "arrival_mode IN ('walk_in', 'ambulance', 'referral', 'police', 'other')",
            name="ck_emergency_visit_arrival_mode",
        ),
        CheckConstraint(
            "status IN ('arrived', 'waiting', 'in_treatment', 'completed', 'closed', "
            "'left_without_being_seen', 'cancelled')",
            name="ck_emergency_visit_status",
        ),
        CheckConstraint(
            "priority IN ('untriaged', 'resuscitation', 'emergent', 'urgent', 'less_urgent', 'non_urgent')",
            name="ck_emergency_visit_priority",
        ),
        CheckConstraint(
            "disposition IS NULL OR disposition IN "
            "('discharged', 'admission_requested', 'referred', 'transfer_requested', 'left_without_being_seen')",
            name="ck_emergency_visit_disposition",
        ),
        Index(
            "uq_emergency_active_patient",
            "hospital_id", "patient_id", unique=True,
            postgresql_where=text("status IN ('arrived', 'waiting', 'in_treatment')"),
        ),
        Index("ix_emergency_queue", "hospital_id", "department_id", "status", "priority", "arrival_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    arrival_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    arrival_note: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="arrived")
    priority: Mapped[str] = mapped_column(String(24), nullable=False, default="untriaged")
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    treatment_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_clinician_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    disposition: Mapped[str | None] = mapped_column(String(32))
    disposition_note: Mapped[str | None] = mapped_column(Text)
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class EmergencyTriageAssessment(Base):
    __tablename__ = "emergency_triage_assessments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "visit_id"],
            ["emergency_visits.hospital_id", "emergency_visits.id"],
            name="fk_emergency_triage_visit",
        ),
        UniqueConstraint("hospital_id", "visit_id", "revision", name="uq_emergency_triage_revision"),
        CheckConstraint(
            "triage_level IN ('resuscitation', 'emergent', 'urgent', 'less_urgent', 'non_urgent')",
            name="ck_emergency_triage_level",
        ),
        CheckConstraint("revision >= 1", name="ck_emergency_triage_revision"),
        CheckConstraint("pain_score IS NULL OR pain_score BETWEEN 0 AND 10", name="ck_emergency_triage_pain"),
        CheckConstraint("heart_rate IS NULL OR heart_rate BETWEEN 1 AND 300", name="ck_emergency_triage_hr"),
        CheckConstraint("respiratory_rate IS NULL OR respiratory_rate BETWEEN 1 AND 100", name="ck_emergency_triage_rr"),
        CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_emergency_triage_temp"),
        CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_emergency_triage_systolic"),
        CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_emergency_triage_diastolic"),
        CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_emergency_triage_spo2"),
        CheckConstraint(
            "red_flag_present = false OR (red_flag_note IS NOT NULL AND length(trim(red_flag_note)) >= 3)",
            name="ck_emergency_triage_red_flag_note",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    triage_level: Mapped[str] = mapped_column(String(24), nullable=False)
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False)
    red_flag_present: Mapped[bool] = mapped_column(default=False, nullable=False)
    red_flag_note: Mapped[str | None] = mapped_column(Text)
    heart_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    respiratory_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    systolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    diastolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    spo2_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pain_score: Mapped[int | None] = mapped_column(Integer)
    consciousness_level: Mapped[str | None] = mapped_column(String(16))
    clinical_notes: Mapped[str | None] = mapped_column(Text)
    assessed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmergencyCareEvent(Base):
    __tablename__ = "emergency_care_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "visit_id"],
            ["emergency_visits.hospital_id", "emergency_visits.id"],
            name="fk_emergency_event_visit",
        ),
        CheckConstraint(
            "event_type IN ('assessment', 'intervention', 'procedure', 'reassessment', 'handover')",
            name="ck_emergency_event_type",
        ),
        CheckConstraint("length(trim(description)) >= 3", name="ck_emergency_event_description"),
        Index("ix_emergency_event_visit", "hospital_id", "visit_id", "performed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    performed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmergencyNote(Base):
    __tablename__ = "emergency_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "visit_id"],
            ["emergency_visits.hospital_id", "emergency_visits.id"],
            name="fk_emergency_note_visit",
        ),
        CheckConstraint(
            "note_type IN ('progress', 'handover', 'incident', 'discharge', 'other')",
            name="ck_emergency_note_type",
        ),
        CheckConstraint("length(trim(note_text)) >= 3", name="ck_emergency_note_text"),
        Index("ix_emergency_note_visit", "hospital_id", "visit_id", "signed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note_type: Mapped[str] = mapped_column(String(24), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
