import uuid
from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TelemedicineSession(Base):
    __tablename__ = "telemedicine_sessions"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_telemedicine_session_patient"),
        ForeignKeyConstraint(["hospital_id", "provider_employee_profile_id", "provider_user_id"], ["employee_profiles.hospital_id", "employee_profiles.id", "employee_profiles.user_id"], name="fk_telemedicine_session_provider_employee"),
        ForeignKeyConstraint(["hospital_id", "provider_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_telemedicine_session_provider_membership"),
        ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_telemedicine_session_department"),
        ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_telemedicine_session_consent"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_telemedicine_session_encounter"),
        UniqueConstraint("hospital_id", "id", "patient_id", name="uq_telemedicine_session_hospital_id_patient"),
        CheckConstraint("status IN ('scheduled', 'patient_ready', 'in_progress', 'completed', 'cancelled', 'no_show')", name="ck_telemedicine_session_status"),
        CheckConstraint("scheduled_end > scheduled_start AND scheduled_end <= scheduled_start + interval '2 hours'", name="ck_telemedicine_session_duration"),
        CheckConstraint("length(trim(visit_reason)) >= 3", name="ck_telemedicine_session_reason"),
        CheckConstraint("patient_location_reference IS NULL OR patient_location_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_telemedicine_location_ref"),
        CheckConstraint("emergency_contact_reference IS NULL OR emergency_contact_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_telemedicine_emergency_ref"),
        CheckConstraint("(status IN ('scheduled', 'cancelled', 'no_show') AND (status != 'scheduled' OR (patient_ready_at IS NULL AND patient_ready_by_user_id IS NULL AND patient_location_reference IS NULL AND emergency_contact_reference IS NULL AND safety_confirmed_at IS NULL AND safety_confirmed_by_user_id IS NULL AND patient_identity_confirmed = false AND privacy_confirmed = false AND emergency_plan_acknowledged = false))) OR (status IN ('patient_ready', 'in_progress', 'completed') AND patient_ready_at IS NOT NULL AND patient_ready_by_user_id IS NOT NULL AND patient_location_reference IS NOT NULL AND emergency_contact_reference IS NOT NULL AND safety_confirmed_at IS NOT NULL AND safety_confirmed_by_user_id IS NOT NULL AND patient_identity_confirmed = true AND privacy_confirmed = true AND emergency_plan_acknowledged = true)", name="ck_telemedicine_safety_state"),
        CheckConstraint("(status IN ('scheduled', 'patient_ready', 'cancelled', 'no_show') AND encounter_id IS NULL AND started_at IS NULL AND started_by_user_id IS NULL AND ended_at IS NULL AND ended_by_user_id IS NULL) OR (status = 'in_progress' AND encounter_id IS NOT NULL AND started_at IS NOT NULL AND started_by_user_id IS NOT NULL AND ended_at IS NULL AND ended_by_user_id IS NULL) OR (status = 'completed' AND encounter_id IS NOT NULL AND started_at IS NOT NULL AND started_by_user_id IS NOT NULL AND ended_at IS NOT NULL AND ended_by_user_id IS NOT NULL AND ended_at > started_at)", name="ck_telemedicine_session_time_state"),
        CheckConstraint("(status IN ('cancelled', 'no_show') AND cancelled_by_user_id IS NOT NULL AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL) OR (status NOT IN ('cancelled', 'no_show') AND cancelled_by_user_id IS NULL AND cancelled_at IS NULL AND cancellation_reason IS NULL)", name="ck_telemedicine_session_cancel_state"),
        Index("ix_telemedicine_patient_schedule", "hospital_id", "patient_id", "scheduled_start", "status"),
        Index("ix_telemedicine_provider_schedule", "hospital_id", "provider_user_id", "scheduled_start", "status"),
        Index("ix_telemedicine_department_schedule", "hospital_id", "department_id", "scheduled_start", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_employee_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    consent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    visit_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="scheduled")
    patient_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    patient_ready_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    patient_location_reference: Mapped[str | None] = mapped_column(String(80))
    emergency_contact_reference: Mapped[str | None] = mapped_column(String(80))
    safety_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safety_confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    patient_identity_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    privacy_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    emergency_plan_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(1000))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TelemedicineClinicalNote(Base):
    __tablename__ = "telemedicine_clinical_notes"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "session_id", "patient_id"], ["telemedicine_sessions.hospital_id", "telemedicine_sessions.id", "telemedicine_sessions.patient_id"], name="fk_telemedicine_note_session"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_telemedicine_note_encounter"),
        UniqueConstraint("hospital_id", "id", "patient_id", name="uq_telemedicine_note_hospital_id_patient"),
        CheckConstraint("note_type IN ('consultation', 'assessment', 'plan', 'follow_up', 'safety_plan', 'referral')", name="ck_telemedicine_note_type"),
        CheckConstraint("length(trim(note_text)) >= 10", name="ck_telemedicine_note_text"),
        CheckConstraint("signed_at IS NOT NULL", name="ck_telemedicine_note_signed"),
        Index("ix_telemedicine_note_session", "hospital_id", "session_id", "created_at"),
        Index("ix_telemedicine_note_patient", "hospital_id", "patient_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note_type: Mapped[str] = mapped_column(String(24), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TelemedicineEvent(Base):
    __tablename__ = "telemedicine_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "session_id", "patient_id"], ["telemedicine_sessions.hospital_id", "telemedicine_sessions.id", "telemedicine_sessions.patient_id"], name="fk_telemedicine_event_session"),
        UniqueConstraint("hospital_id", "id", name="uq_telemedicine_event_hospital_id"),
        CheckConstraint("event_type IN ('session_scheduled', 'patient_ready', 'session_started', 'note_signed', 'session_completed', 'session_cancelled', 'session_no_show')", name="ck_telemedicine_event_type"),
        Index("ix_telemedicine_event_history", "hospital_id", "session_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(48), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
