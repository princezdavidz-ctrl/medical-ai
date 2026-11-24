import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Integer, Numeric, String, Text, UniqueConstraint, Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ICUStay(Base):
    __tablename__ = "icu_stays"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "admission_id", "patient_id"],
            ["inpatient_admissions.hospital_id", "inpatient_admissions.id", "inpatient_admissions.patient_id"],
            name="fk_icu_stay_admission_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "bed_assignment_id", "admission_id"],
            ["bed_assignments.hospital_id", "bed_assignments.id", "bed_assignments.admission_id"],
            name="fk_icu_stay_bed_assignment_admission",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_icu_stay_encounter_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "ward_id"],
            ["wards.hospital_id", "wards.id"],
            name="fk_icu_stay_ward",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_icu_stay_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_icu_stay_hospital_id_id"),
        CheckConstraint(
            "status IN ('active', 'stepdown_requested', 'closed')",
            name="ck_icu_stay_status",
        ),
        Index(
            "uq_icu_active_admission", "hospital_id", "admission_id",
            unique=True, postgresql_where=text("status IN ('active', 'stepdown_requested')"),
        ),
        Index("ix_icu_stay_department_status", "hospital_id", "department_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    admission_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    bed_assignment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ward_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    started_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    admission_reason: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    stepdown_requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    stepdown_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ICUObservation(Base):
    __tablename__ = "icu_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "stay_id"],
            ["icu_stays.hospital_id", "icu_stays.id"],
            name="fk_icu_observation_stay",
        ),
        CheckConstraint("heart_rate IS NULL OR heart_rate BETWEEN 1 AND 300", name="ck_icu_obs_hr"),
        CheckConstraint("respiratory_rate IS NULL OR respiratory_rate BETWEEN 1 AND 100", name="ck_icu_obs_rr"),
        CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_icu_obs_temp"),
        CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_icu_obs_systolic"),
        CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_icu_obs_diastolic"),
        CheckConstraint("systolic_bp IS NULL OR diastolic_bp IS NULL OR systolic_bp > diastolic_bp", name="ck_icu_obs_bp_order"),
        CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_icu_obs_spo2"),
        CheckConstraint("pain_score IS NULL OR pain_score BETWEEN 0 AND 10", name="ck_icu_obs_pain"),
        CheckConstraint("gcs_eye IS NULL OR gcs_eye BETWEEN 1 AND 4", name="ck_icu_obs_gcs_eye"),
        CheckConstraint("gcs_verbal IS NULL OR gcs_verbal BETWEEN 1 AND 5", name="ck_icu_obs_gcs_verbal"),
        CheckConstraint("gcs_motor IS NULL OR gcs_motor BETWEEN 1 AND 6", name="ck_icu_obs_gcs_motor"),
        CheckConstraint("urine_output_ml IS NULL OR urine_output_ml >= 0", name="ck_icu_obs_urine_output"),
        CheckConstraint("fluid_intake_ml IS NULL OR fluid_intake_ml >= 0", name="ck_icu_obs_fluid_intake"),
        CheckConstraint("fluid_output_ml IS NULL OR fluid_output_ml >= 0", name="ck_icu_obs_fluid_output"),
        Index("ix_icu_observation_stay", "hospital_id", "stay_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    stay_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    heart_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    respiratory_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    systolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    diastolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    spo2_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pain_score: Mapped[int | None] = mapped_column(Integer)
    gcs_eye: Mapped[int | None] = mapped_column(Integer)
    gcs_verbal: Mapped[int | None] = mapped_column(Integer)
    gcs_motor: Mapped[int | None] = mapped_column(Integer)
    oxygen_support: Mapped[str | None] = mapped_column(String(120))
    ventilation_mode: Mapped[str | None] = mapped_column(String(120))
    urine_output_ml: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    fluid_intake_ml: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    fluid_output_ml: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ICUCareEvent(Base):
    __tablename__ = "icu_care_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "stay_id"],
            ["icu_stays.hospital_id", "icu_stays.id"],
            name="fk_icu_care_event_stay",
        ),
        CheckConstraint(
            "event_type IN ('assessment', 'intervention', 'procedure', 'airway_support', "
            "'ventilation_change', 'handover', 'other')",
            name="ck_icu_care_event_type",
        ),
        CheckConstraint("length(trim(description)) >= 3", name="ck_icu_care_event_description"),
        Index("ix_icu_care_event_stay", "hospital_id", "stay_id", "performed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    stay_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    performed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ICUProgressNote(Base):
    __tablename__ = "icu_progress_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "stay_id"],
            ["icu_stays.hospital_id", "icu_stays.id"],
            name="fk_icu_progress_note_stay",
        ),
        CheckConstraint(
            "note_type IN ('daily_review', 'progress', 'handover', 'incident', 'other')",
            name="ck_icu_progress_note_type",
        ),
        CheckConstraint("length(trim(note_text)) >= 3", name="ck_icu_progress_note_text"),
        Index("ix_icu_progress_note_stay", "hospital_id", "stay_id", "signed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    stay_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note_type: Mapped[str] = mapped_column(String(24), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
