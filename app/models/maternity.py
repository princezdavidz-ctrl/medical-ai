import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint,
    Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MaternityEpisode(Base):
    __tablename__ = "maternity_episodes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_maternity_episode_mother",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_maternity_episode_encounter_mother",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_maternity_episode_department",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_maternity_episode_hospital_id_id"),
        UniqueConstraint("hospital_id", "id", "patient_id", name="uq_maternity_episode_hospital_id_patient"),
        UniqueConstraint("hospital_id", "patient_id", "pregnancy_number", name="uq_maternity_episode_pregnancy_number"),
        CheckConstraint("pregnancy_number >= 1", name="ck_maternity_episode_pregnancy_number"),
        CheckConstraint("gravida >= 1 AND para >= 0 AND para <= gravida", name="ck_maternity_episode_gravida_para"),
        CheckConstraint("pregnancy_status IN ('antenatal', 'in_labor', 'postpartum', 'ended')", name="ck_maternity_episode_pregnancy_status"),
        CheckConstraint("pregnancy_status != 'ended' OR pregnancy_end_reason IS NOT NULL", name="ck_maternity_episode_end_reason"),
        CheckConstraint("status IN ('active', 'closed')", name="ck_maternity_episode_status"),
        CheckConstraint("closed_reason IS NULL OR length(trim(closed_reason)) >= 3", name="ck_maternity_episode_closed_reason"),
        Index(
            "uq_maternity_active_episode_patient",
            "hospital_id", "patient_id", unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_maternity_episode_department_status", "hospital_id", "department_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pregnancy_number: Mapped[int] = mapped_column(Integer, nullable=False)
    gravida: Mapped[int] = mapped_column(Integer, nullable=False)
    para: Mapped[int] = mapped_column(Integer, nullable=False)
    last_menstrual_period: Mapped[date | None] = mapped_column(Date)
    estimated_due_date: Mapped[date | None] = mapped_column(Date)
    pregnancy_status: Mapped[str] = mapped_column(String(24), nullable=False, default="antenatal")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_reason: Mapped[str | None] = mapped_column(Text)
    pregnancy_end_reason: Mapped[str | None] = mapped_column(String(24))


class MaternityAntenatalVisit(Base):
    __tablename__ = "maternity_antenatal_visits"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "episode_id"],
            ["maternity_episodes.hospital_id", "maternity_episodes.id"],
            name="fk_maternity_antenatal_visit_episode",
        ),
        CheckConstraint("gestational_age_weeks BETWEEN 0 AND 45", name="ck_antenatal_gestational_weeks"),
        CheckConstraint("gestational_age_days BETWEEN 0 AND 6", name="ck_antenatal_gestational_days"),
        CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_antenatal_systolic"),
        CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_antenatal_diastolic"),
        CheckConstraint("systolic_bp IS NULL OR diastolic_bp IS NULL OR systolic_bp > diastolic_bp", name="ck_antenatal_bp_order"),
        CheckConstraint("weight_kg IS NULL OR weight_kg BETWEEN 0.2 AND 500", name="ck_antenatal_weight"),
        CheckConstraint("fetal_heart_rate IS NULL OR fetal_heart_rate BETWEEN 50 AND 240", name="ck_antenatal_fhr"),
        CheckConstraint("fundal_height_cm IS NULL OR fundal_height_cm BETWEEN 0 AND 60", name="ck_antenatal_fundal_height"),
        Index("ix_antenatal_visit_episode_date", "hospital_id", "episode_id", "visited_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    episode_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    gestational_age_weeks: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    gestational_age_days: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    systolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    diastolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fetal_heart_rate: Mapped[int | None] = mapped_column(Integer)
    fundal_height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    fetal_movement_reported: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LaborRecord(Base):
    __tablename__ = "labor_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "episode_id"],
            ["maternity_episodes.hospital_id", "maternity_episodes.id"],
            name="fk_labor_record_episode",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_labor_record_hospital_id_id"),
        UniqueConstraint("hospital_id", "id", "episode_id", name="uq_labor_record_hospital_id_episode"),
        UniqueConstraint("hospital_id", "episode_id", name="uq_labor_record_episode"),
        CheckConstraint("status IN ('latent', 'active', 'second_stage', 'delivered', 'ended')", name="ck_labor_record_status"),
        CheckConstraint("onset_type IN ('spontaneous', 'induced', 'augmented', 'other')", name="ck_labor_record_onset"),
        CheckConstraint("membrane_status IN ('intact', 'ruptured', 'unknown')", name="ck_labor_record_membranes"),
        CheckConstraint("presentation IN ('cephalic', 'breech', 'transverse', 'other', 'unknown')", name="ck_labor_record_presentation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    episode_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    lead_midwife_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="latent")
    onset_type: Mapped[str] = mapped_column(String(24), nullable=False)
    membrane_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    presentation: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LaborObservation(Base):
    __tablename__ = "labor_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "labor_record_id"],
            ["labor_records.hospital_id", "labor_records.id"],
            name="fk_labor_observation_record",
        ),
        CheckConstraint("labor_stage IN ('latent', 'active', 'second_stage')", name="ck_labor_observation_stage"),
        CheckConstraint("membrane_status IS NULL OR membrane_status IN ('intact', 'ruptured', 'unknown')", name="ck_labor_observation_membranes"),
        CheckConstraint("cervical_dilation_cm IS NULL OR cervical_dilation_cm BETWEEN 0 AND 10", name="ck_labor_cervical_dilation"),
        CheckConstraint("fetal_heart_rate IS NULL OR fetal_heart_rate BETWEEN 50 AND 240", name="ck_labor_fhr"),
        CheckConstraint("contractions_per_10_min IS NULL OR contractions_per_10_min BETWEEN 0 AND 10", name="ck_labor_contractions"),
        CheckConstraint("contraction_duration_seconds IS NULL OR contraction_duration_seconds BETWEEN 0 AND 300", name="ck_labor_contraction_duration"),
        CheckConstraint("maternal_heart_rate IS NULL OR maternal_heart_rate BETWEEN 1 AND 300", name="ck_labor_maternal_hr"),
        CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_labor_systolic"),
        CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_labor_diastolic"),
        CheckConstraint("systolic_bp IS NULL OR diastolic_bp IS NULL OR systolic_bp > diastolic_bp", name="ck_labor_bp_order"),
        CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_labor_temperature"),
        CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_labor_spo2"),
        Index("ix_labor_observation_record_time", "hospital_id", "labor_record_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    labor_record_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    labor_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    cervical_dilation_cm: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    fetal_heart_rate: Mapped[int | None] = mapped_column(Integer)
    contractions_per_10_min: Mapped[int | None] = mapped_column(Integer)
    contraction_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    maternal_heart_rate: Mapped[int | None] = mapped_column(Integer)
    systolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    diastolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    spo2_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    membrane_status: Mapped[str | None] = mapped_column(String(24))
    amniotic_fluid_description: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DeliveryRecord(Base):
    __tablename__ = "maternity_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "labor_record_id", "episode_id"],
            ["labor_records.hospital_id", "labor_records.id", "labor_records.episode_id"],
            name="fk_maternity_delivery_labor_episode",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "episode_id", "mother_patient_id"],
            ["maternity_episodes.hospital_id", "maternity_episodes.id", "maternity_episodes.patient_id"],
            name="fk_maternity_delivery_episode_mother",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "surgical_case_id", "mother_patient_id"],
            ["surgical_cases.hospital_id", "surgical_cases.id", "surgical_cases.patient_id"],
            name="fk_maternity_delivery_surgical_case_mother",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_maternity_delivery_hospital_id_id"),
        UniqueConstraint("hospital_id", "id", "mother_patient_id", name="uq_maternity_delivery_hospital_id_mother"),
        UniqueConstraint("hospital_id", "labor_record_id", name="uq_maternity_delivery_labor"),
        UniqueConstraint("hospital_id", "episode_id", name="uq_maternity_delivery_episode"),
        UniqueConstraint("hospital_id", "surgical_case_id", name="uq_maternity_delivery_surgical_case"),
        CheckConstraint("delivery_mode IN ('spontaneous_vaginal', 'assisted_vaginal', 'cesarean', 'breech', 'other')", name="ck_maternity_delivery_mode"),
        CheckConstraint("estimated_blood_loss_ml IS NULL OR estimated_blood_loss_ml BETWEEN 0 AND 50000", name="ck_maternity_delivery_blood_loss"),
        CheckConstraint("placenta_delivered_at IS NULL OR placenta_delivered_at >= delivered_at", name="ck_maternity_delivery_placenta_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    labor_record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    episode_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    mother_patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    surgical_case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    delivered_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    delivery_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    placenta_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_blood_loss_ml: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    complications: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NewbornRecord(Base):
    __tablename__ = "maternity_newborns"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "delivery_id", "mother_patient_id"],
            ["maternity_deliveries.hospital_id", "maternity_deliveries.id", "maternity_deliveries.mother_patient_id"],
            name="fk_maternity_newborn_delivery_mother",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "mother_patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_maternity_newborn_mother",
        ),
        ForeignKeyConstraint(
            ["hospital_id", "newborn_patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_maternity_newborn_patient",
        ),
        UniqueConstraint("hospital_id", "id", name="uq_maternity_newborn_hospital_id_id"),
        UniqueConstraint("hospital_id", "delivery_id", "birth_order", name="uq_maternity_newborn_birth_order"),
        CheckConstraint("birth_order >= 1", name="ck_maternity_newborn_birth_order"),
        CheckConstraint("sex IN ('female', 'male', 'intersex', 'unknown')", name="ck_maternity_newborn_sex"),
        CheckConstraint("outcome IN ('live_birth', 'stillbirth', 'neonatal_death')", name="ck_maternity_newborn_outcome"),
        CheckConstraint("birth_weight_g IS NULL OR birth_weight_g BETWEEN 100 AND 10000", name="ck_maternity_newborn_weight"),
        CheckConstraint("length_cm IS NULL OR length_cm BETWEEN 10 AND 100", name="ck_maternity_newborn_length"),
        CheckConstraint("head_circumference_cm IS NULL OR head_circumference_cm BETWEEN 10 AND 70", name="ck_maternity_newborn_head"),
        CheckConstraint("apgar_1_minute IS NULL OR apgar_1_minute BETWEEN 0 AND 10", name="ck_maternity_newborn_apgar1"),
        CheckConstraint("apgar_5_minute IS NULL OR apgar_5_minute BETWEEN 0 AND 10", name="ck_maternity_newborn_apgar5"),
        CheckConstraint("apgar_10_minute IS NULL OR apgar_10_minute BETWEEN 0 AND 10", name="ck_maternity_newborn_apgar10"),
        CheckConstraint("outcome != 'stillbirth' OR newborn_patient_id IS NULL", name="ck_maternity_newborn_patient_only_live"),
        Index("ix_maternity_newborn_mother", "hospital_id", "mother_patient_id", "birth_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    delivery_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    mother_patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    newborn_patient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    birth_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sex: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    birth_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    birth_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    length_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    head_circumference_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    apgar_1_minute: Mapped[int | None] = mapped_column(Integer)
    apgar_5_minute: Mapped[int | None] = mapped_column(Integer)
    apgar_10_minute: Mapped[int | None] = mapped_column(Integer)
    resuscitation_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)


class PostpartumObservation(Base):
    __tablename__ = "maternity_postpartum_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "episode_id"],
            ["maternity_episodes.hospital_id", "maternity_episodes.id"],
            name="fk_maternity_postpartum_episode",
        ),
        CheckConstraint("maternal_heart_rate IS NULL OR maternal_heart_rate BETWEEN 1 AND 300", name="ck_postpartum_hr"),
        CheckConstraint("systolic_bp IS NULL OR systolic_bp BETWEEN 30 AND 300", name="ck_postpartum_systolic"),
        CheckConstraint("diastolic_bp IS NULL OR diastolic_bp BETWEEN 20 AND 200", name="ck_postpartum_diastolic"),
        CheckConstraint("systolic_bp IS NULL OR diastolic_bp IS NULL OR systolic_bp > diastolic_bp", name="ck_postpartum_bp_order"),
        CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_postpartum_temperature"),
        CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_postpartum_spo2"),
        CheckConstraint("estimated_blood_loss_ml IS NULL OR estimated_blood_loss_ml BETWEEN 0 AND 50000", name="ck_postpartum_blood_loss"),
        CheckConstraint("uterine_tone IN ('firm', 'boggy', 'not_assessed')", name="ck_postpartum_uterine_tone"),
        CheckConstraint("lochia IN ('normal', 'heavy', 'not_assessed')", name="ck_postpartum_lochia"),
        Index("ix_postpartum_episode_time", "hospital_id", "episode_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    episode_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    maternal_heart_rate: Mapped[int | None] = mapped_column(Integer)
    systolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    diastolic_bp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    spo2_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    estimated_blood_loss_ml: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    uterine_tone: Mapped[str] = mapped_column(String(24), nullable=False, default="not_assessed")
    lochia: Mapped[str] = mapped_column(String(24), nullable=False, default="not_assessed")
    breastfeeding_initiated: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NewbornObservation(Base):
    __tablename__ = "maternity_newborn_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "newborn_record_id"],
            ["maternity_newborns.hospital_id", "maternity_newborns.id"],
            name="fk_maternity_newborn_observation_record",
        ),
        CheckConstraint("temperature_c IS NULL OR temperature_c BETWEEN 25 AND 45", name="ck_newborn_obs_temp"),
        CheckConstraint("heart_rate IS NULL OR heart_rate BETWEEN 1 AND 300", name="ck_newborn_obs_hr"),
        CheckConstraint("respiratory_rate IS NULL OR respiratory_rate BETWEEN 1 AND 150", name="ck_newborn_obs_rr"),
        CheckConstraint("spo2_percent IS NULL OR spo2_percent BETWEEN 0 AND 100", name="ck_newborn_obs_spo2"),
        CheckConstraint("feeding_status IN ('breastfeeding', 'expressed_milk', 'formula', 'not_feeding', 'not_assessed')", name="ck_newborn_obs_feeding"),
        CheckConstraint("urine_output_count IS NULL OR urine_output_count BETWEEN 0 AND 100", name="ck_newborn_obs_urine_count"),
        CheckConstraint("stool_count IS NULL OR stool_count BETWEEN 0 AND 100", name="ck_newborn_obs_stool_count"),
        Index("ix_newborn_observation_record_time", "hospital_id", "newborn_record_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    newborn_record_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    heart_rate: Mapped[int | None] = mapped_column(Integer)
    respiratory_rate: Mapped[int | None] = mapped_column(Integer)
    spo2_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    feeding_status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_assessed")
    urine_output_count: Mapped[int | None] = mapped_column(Integer)
    stool_count: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaternityNote(Base):
    __tablename__ = "maternity_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["hospital_id", "episode_id"],
            ["maternity_episodes.hospital_id", "maternity_episodes.id"],
            name="fk_maternity_note_episode",
        ),
        CheckConstraint("note_type IN ('antenatal', 'labor', 'delivery', 'postpartum', 'handover', 'other')", name="ck_maternity_note_type"),
        CheckConstraint("length(trim(note_text)) >= 3", name="ck_maternity_note_text"),
        Index("ix_maternity_note_episode", "hospital_id", "episode_id", "signed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    episode_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note_type: Mapped[str] = mapped_column(String(24), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
