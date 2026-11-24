import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Numeric, SmallInteger, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NursingAssessment(Base):
    __tablename__ = "nursing_assessments"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_nursingassessment_encounter_patient"),
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_nursing_assessment_patient"),
        ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_nursing_assessment_department"),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id"],
            ["encounters.hospital_id", "encounters.id"],
            name="fk_nursing_assessment_encounter",
        ),
        CheckConstraint(
            "assessment_type IN ('admission', 'shift', 'focused', 'discharge')",
            name="ck_nursing_assessment_type",
        ),
        CheckConstraint(
            "pain_score IS NULL OR pain_score BETWEEN 0 AND 10",
            name="ck_nursing_assessment_pain",
        ),
        CheckConstraint(
            "fall_risk_level IS NULL OR fall_risk_level IN ('low', 'moderate', 'high', 'not_assessed')",
            name="ck_nursing_assessment_fall_risk",
        ),
        CheckConstraint(
            "pressure_injury_risk_level IS NULL OR pressure_injury_risk_level IN ('low', 'moderate', 'high', 'not_assessed')",
            name="ck_nursing_assessment_pressure_risk",
        ),
        Index("ix_nursing_assessment_encounter", "hospital_id", "encounter_id", "assessed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id"), nullable=False)
    assessed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(24), nullable=False)
    general_condition: Mapped[str | None] = mapped_column(String(500))
    mental_status: Mapped[str | None] = mapped_column(String(500))
    mobility_status: Mapped[str | None] = mapped_column(String(500))
    skin_assessment: Mapped[str | None] = mapped_column(Text)
    pain_score: Mapped[int | None] = mapped_column(SmallInteger)
    fall_risk_level: Mapped[str | None] = mapped_column(String(24))
    pressure_injury_risk_level: Mapped[str | None] = mapped_column(String(24))
    nutrition_concerns: Mapped[str | None] = mapped_column(Text)
    nursing_concerns: Mapped[str | None] = mapped_column(Text)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NursingObservation(Base):
    __tablename__ = "nursing_observations"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_nursingobservation_encounter_patient"),
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_nursing_observation_patient"),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id"],
            ["encounters.hospital_id", "encounters.id"],
            name="fk_nursing_observation_encounter",
        ),
        CheckConstraint("heart_rate IS NULL OR heart_rate BETWEEN 1 AND 300", name="ck_nursing_obs_hr"),
        CheckConstraint("respiratory_rate IS NULL OR respiratory_rate BETWEEN 1 AND 100", name="ck_nursing_obs_rr"),
        CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_nursing_obs_temp"),
        CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_nursing_obs_systolic"),
        CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_nursing_obs_diastolic"),
        CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_nursing_obs_spo2"),
        CheckConstraint("pain_score IS NULL OR pain_score BETWEEN 0 AND 10", name="ck_nursing_obs_pain"),
        CheckConstraint("systolic_bp IS NULL OR diastolic_bp IS NULL OR systolic_bp > diastolic_bp", name="ck_nursing_obs_bp_order"),
        CheckConstraint("intake_ml IS NULL OR intake_ml >= 0", name="ck_nursing_obs_intake"),
        CheckConstraint("output_ml IS NULL OR output_ml >= 0", name="ck_nursing_obs_output"),
        Index("ix_nursing_observation_encounter", "hospital_id", "encounter_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    heart_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    respiratory_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    systolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    diastolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    spo2_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pain_score: Mapped[int | None] = mapped_column(SmallInteger)
    consciousness_level: Mapped[str | None] = mapped_column(String(16))
    oxygen_delivery: Mapped[str | None] = mapped_column(String(120))
    intake_ml: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    output_ml: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NursingNote(Base):
    __tablename__ = "nursing_notes"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_nursingnote_encounter_patient"),
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_nursing_note_patient"),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id"],
            ["encounters.hospital_id", "encounters.id"],
            name="fk_nursing_note_encounter",
        ),
        CheckConstraint(
            "note_type IN ('shift_handover', 'progress', 'incident', 'discharge', 'other')",
            name="ck_nursing_note_type",
        ),
        CheckConstraint("length(trim(note_text)) >= 3", name="ck_nursing_note_text"),
        Index("ix_nursing_note_encounter", "hospital_id", "encounter_id", "signed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note_type: Mapped[str] = mapped_column(String(24), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NursingCarePlan(Base):
    __tablename__ = "nursing_care_plans"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_nursingcareplan_encounter_patient"),
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_nursing_care_plan_patient"),
        ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_nursing_care_plan_department"),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id"],
            ["encounters.hospital_id", "encounters.id"],
            name="fk_nursing_care_plan_encounter",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')",
            name="ck_nursing_care_plan_status",
        ),
        CheckConstraint("length(trim(nursing_diagnosis)) >= 3", name="ck_nursing_care_plan_diagnosis"),
        CheckConstraint("length(trim(goals)) >= 3", name="ck_nursing_care_plan_goals"),
        CheckConstraint("length(trim(interventions)) >= 3", name="ck_nursing_care_plan_interventions"),
        Index("ix_nursing_care_plan_encounter", "hospital_id", "encounter_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    nursing_diagnosis: Mapped[str] = mapped_column(String(1000), nullable=False)
    goals: Mapped[str] = mapped_column(Text, nullable=False)
    interventions: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NursingCarePlanReview(Base):
    __tablename__ = "nursing_care_plan_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "care_plan_id"],
            ["nursing_care_plans.hospital_id", "nursing_care_plans.id"],
            name="fk_nursing_care_plan_review_plan",
        ),
        CheckConstraint(
            "outcome IN ('ongoing', 'achieved', 'partially_achieved', 'not_achieved', 'escalated')",
            name="ck_nursing_care_plan_review_outcome",
        ),
        CheckConstraint("length(trim(evaluation_note)) >= 3", name="ck_nursing_care_plan_review_note"),
        Index("ix_nursing_care_plan_review_plan", "hospital_id", "care_plan_id", "reviewed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    care_plan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    evaluation_note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
