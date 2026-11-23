import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Numeric, SmallInteger, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.core import TimestampMixin


class OPDVisit(TimestampMixin, Base):
    __tablename__ = "opd_visits"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"],
            name="fk_opd_visit_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id"], ["encounters.hospital_id", "encounters.id"],
            name="fk_opd_visit_encounter",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"],
            name="fk_opd_visit_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_opd_visit_hospital_id_id"),
        UniqueConstraint("hospital_id", "encounter_id", name="uq_opd_visit_encounter"),
        UniqueConstraint("hospital_id", "visit_date", "queue_token", name="uq_opd_visit_queue_token"),
        CheckConstraint(
            "visit_type IN ('walk_in', 'appointment', 'referral', 'transfer')",
            name="ck_opd_visit_type",
        ),
        CheckConstraint(
            "status IN ('registered', 'arrived', 'waiting', 'in_consultation', "
            "'completed', 'closed', 'cancelled', 'left_without_being_seen')",
            name="ck_opd_visit_status",
        ),
        CheckConstraint(
            "priority IN ('emergency', 'very_urgent', 'urgent', 'standard', 'non_urgent')",
            name="ck_opd_visit_priority",
        ),
        CheckConstraint(
            "disposition IS NULL OR disposition IN "
            "('discharged', 'admission_requested', 'referred', 'transfer_requested', 'left_without_being_seen')",
            name="ck_opd_visit_disposition",
        ),
        Index("ix_opd_queue", "hospital_id", "department_id", "visit_date", "status", "priority"),
        Index("ix_opd_patient_history", "hospital_id", "patient_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    queue_token: Mapped[str] = mapped_column(String(12), nullable=False)
    visit_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="registered")
    priority: Mapped[str] = mapped_column(String(24), nullable=False, default="standard")
    arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    triage_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consultation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_clinician_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    disposition: Mapped[str | None] = mapped_column(String(32))
    disposition_note: Mapped[str | None] = mapped_column(Text)
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class OPDTriageAssessment(Base):
    __tablename__ = "opd_triage_assessments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "visit_id"], ["opd_visits.hospital_id", "opd_visits.id"],
            name="fk_opd_triage_visit", ondelete="CASCADE",
        ),
        UniqueConstraint("hospital_id", "visit_id", name="uq_opd_triage_visit"),
        CheckConstraint(
            "triage_level IN ('emergency', 'very_urgent', 'urgent', 'standard', 'non_urgent')",
            name="ck_opd_triage_level",
        ),
        CheckConstraint("heart_rate IS NULL OR heart_rate BETWEEN 1 AND 300", name="ck_opd_triage_hr"),
        CheckConstraint("respiratory_rate IS NULL OR respiratory_rate BETWEEN 1 AND 100", name="ck_opd_triage_rr"),
        CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_opd_triage_temp"),
        CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_opd_triage_systolic"),
        CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_opd_triage_diastolic"),
        CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_opd_triage_spo2"),
        CheckConstraint("weight_kg IS NULL OR weight_kg BETWEEN 0.2 AND 500", name="ck_opd_triage_weight"),
        CheckConstraint("height_cm IS NULL OR height_cm BETWEEN 20 AND 250", name="ck_opd_triage_height"),
        CheckConstraint("pain_score IS NULL OR pain_score BETWEEN 0 AND 10", name="ck_opd_triage_pain"),
        CheckConstraint(
            "red_flag_present = false OR (red_flag_note IS NOT NULL AND length(trim(red_flag_note)) >= 3)",
            name="ck_opd_triage_red_flag_note",
        ),
        Index("ix_opd_triage_hospital_visit", "hospital_id", "visit_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    assessed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    triage_level: Mapped[str] = mapped_column(String(24), nullable=False)
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False)
    red_flag_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    red_flag_note: Mapped[str | None] = mapped_column(Text)
    heart_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    respiratory_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    systolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    diastolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    spo2_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    pain_score: Mapped[int | None] = mapped_column(SmallInteger)
    consciousness_level: Mapped[str | None] = mapped_column(String(12))
    clinical_notes: Mapped[str | None] = mapped_column(Text)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OPDConsultationNote(Base):
    __tablename__ = "opd_consultation_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "visit_id"], ["opd_visits.hospital_id", "opd_visits.id"],
            name="fk_opd_consultation_visit", ondelete="CASCADE",
        ),
        UniqueConstraint("hospital_id", "visit_id", name="uq_opd_consultation_visit"),
        CheckConstraint("length(trim(assessment)) >= 3", name="ck_opd_consultation_assessment"),
        CheckConstraint("length(trim(plan)) >= 3", name="ck_opd_consultation_plan"),
        Index("ix_opd_consultation_hospital_visit", "hospital_id", "visit_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    clinician_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    subjective: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    assessment: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    follow_up: Mapped[str | None] = mapped_column(Text)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OPDDiagnosis(Base):
    __tablename__ = "opd_diagnoses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "visit_id"], ["opd_visits.hospital_id", "opd_visits.id"],
            name="fk_opd_diagnosis_visit", ondelete="CASCADE",
        ),
        CheckConstraint(
            "certainty IN ('suspected', 'provisional', 'confirmed', 'ruled_out')",
            name="ck_opd_diagnosis_certainty",
        ),
        Index("ix_opd_diagnosis_hospital_visit", "hospital_id", "visit_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    diagnosis_text: Mapped[str] = mapped_column(String(500), nullable=False)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clinical_concepts.id"))
    certainty: Mapped[str] = mapped_column(String(24), nullable=False, default="provisional")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
