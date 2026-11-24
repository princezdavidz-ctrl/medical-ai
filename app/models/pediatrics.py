import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Numeric, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PediatricCareRecord(Base):
    __tablename__ = "pediatric_care_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_pediatric_care_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_pediatric_care_encounter_patient",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_pediatric_care_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_pediatric_care_hospital_id"),
        UniqueConstraint("hospital_id", "encounter_id", name="uq_pediatric_care_encounter"),
        CheckConstraint("status IN ('active', 'closed')", name="ck_pediatric_care_status"),
        CheckConstraint(
            "(status = 'active' AND closed_at IS NULL) OR "
            "(status = 'closed' AND closed_at IS NOT NULL)",
            name="ck_pediatric_care_closure_state",
        ),
        Index("ix_pediatric_care_patient_created", "hospital_id", "patient_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PediatricGrowthObservation(Base):
    __tablename__ = "pediatric_growth_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "care_record_id"],
            ["pediatric_care_records.hospital_id", "pediatric_care_records.id"],
            name="fk_pediatric_growth_care_record",
        ),
        CheckConstraint("weight_kg IS NULL OR weight_kg BETWEEN 0.2 AND 300", name="ck_pediatric_growth_weight"),
        CheckConstraint("height_cm IS NULL OR height_cm BETWEEN 20 AND 250", name="ck_pediatric_growth_height"),
        CheckConstraint("head_circumference_cm IS NULL OR head_circumference_cm BETWEEN 10 AND 100", name="ck_pediatric_growth_head"),
        CheckConstraint("mid_upper_arm_cm IS NULL OR mid_upper_arm_cm BETWEEN 5 AND 60", name="ck_pediatric_growth_muac"),
        CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_pediatric_growth_temperature"),
        CheckConstraint("source IN ('measured', 'reported')", name="ck_pediatric_growth_source"),
        Index("ix_pediatric_growth_record_time", "hospital_id", "care_record_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    care_record_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    head_circumference_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    mid_upper_arm_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="measured")
    notes: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PediatricDevelopmentalScreening(Base):
    __tablename__ = "pediatric_developmental_screenings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "care_record_id"],
            ["pediatric_care_records.hospital_id", "pediatric_care_records.id"],
            name="fk_pediatric_screening_care_record",
        ),
        CheckConstraint(
            "domain IN ('gross_motor', 'fine_motor', 'language', 'cognitive', 'social_emotional', 'adaptive', 'general')",
            name="ck_pediatric_screening_domain",
        ),
        CheckConstraint(
            "outcome IN ('age_appropriate', 'monitor', 'refer', 'not_assessed', 'unable_to_assess')",
            name="ck_pediatric_screening_outcome",
        ),
        Index("ix_pediatric_screening_record_date", "hospital_id", "care_record_id", "screened_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    care_record_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    instrument_name: Mapped[str] = mapped_column(String(160), nullable=False)
    instrument_version: Mapped[str | None] = mapped_column(String(80))
    domain: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    referral_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    screened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PediatricImmunizationHistory(Base):
    __tablename__ = "pediatric_immunization_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "care_record_id"],
            ["pediatric_care_records.hospital_id", "pediatric_care_records.id"],
            name="fk_pediatric_immunization_care_record",
        ),
        CheckConstraint(
            "record_status IN ('administered', 'reported', 'deferred', 'declined', 'unknown')",
            name="ck_pediatric_immunization_status",
        ),
        CheckConstraint(
            "source IN ('facility_record', 'caregiver_report', 'external_record')",
            name="ck_pediatric_immunization_source",
        ),
        CheckConstraint(
            "record_status != 'administered' OR administered_at IS NOT NULL",
            name="ck_pediatric_immunization_administered_at",
        ),
        Index("ix_pediatric_immunization_record_date", "hospital_id", "care_record_id", "administered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    care_record_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    vaccine_label: Mapped[str] = mapped_column(String(160), nullable=False)
    dose_label: Mapped[str | None] = mapped_column(String(80))
    record_status: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="facility_record")
    administered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    batch_reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PediatricClinicalNote(Base):
    __tablename__ = "pediatric_clinical_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "care_record_id"],
            ["pediatric_care_records.hospital_id", "pediatric_care_records.id"],
            name="fk_pediatric_note_care_record",
        ),
        CheckConstraint(
            "note_type IN ('assessment', 'progress', 'handover', 'discharge', 'other')",
            name="ck_pediatric_note_type",
        ),
        CheckConstraint("length(trim(note_text)) >= 3", name="ck_pediatric_note_text"),
        Index("ix_pediatric_note_record_time", "hospital_id", "care_record_id", "signed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    care_record_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    authored_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note_type: Mapped[str] = mapped_column(String(24), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
