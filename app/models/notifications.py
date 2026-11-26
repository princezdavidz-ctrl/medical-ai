import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Integer, JSON, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_notification_preference_membership"),
        UniqueConstraint("hospital_id", "user_id", name="uq_notification_preference_hospital_user"),
        CheckConstraint("locale ~ '^[a-z]{2}(-[A-Z]{2})?$'", name="ck_notification_preference_locale"),
        CheckConstraint("timezone_name <> ''", name="ck_notification_preference_timezone"),
        CheckConstraint("quiet_start IS NULL OR quiet_start ~ '^[0-2][0-9]:[0-5][0-9]$'", name="ck_notification_quiet_start"),
        CheckConstraint("quiet_end IS NULL OR quiet_end ~ '^[0-2][0-9]:[0-5][0-9]$'", name="ck_notification_quiet_end"),
        CheckConstraint("(quiet_start IS NULL) = (quiet_end IS NULL)", name="ck_notification_quiet_pair"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locale: Mapped[str] = mapped_column(String(12), nullable=False, default="en")
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False, default="Africa/Nairobi")
    quiet_start: Mapped[str | None] = mapped_column(String(5))
    quiet_end: Mapped[str | None] = mapped_column(String(5))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint("hospital_id", "template_code", "version", name="uq_notification_template_version"),
        UniqueConstraint("hospital_id", "id", name="uq_notification_template_hospital_id"),
        CheckConstraint("channel IN ('in_app', 'email', 'sms', 'push')", name="ck_notification_template_channel"),
        CheckConstraint("status IN ('draft', 'published', 'retired')", name="ck_notification_template_status"),
        CheckConstraint("content_classification IN ('operational', 'administrative', 'sensitive')", name="ck_notification_template_classification"),
        CheckConstraint("version >= 1", name="ck_notification_template_version"),
        CheckConstraint("length(trim(template_code)) BETWEEN 2 AND 80", name="ck_notification_template_code"),
        CheckConstraint("length(trim(title_template)) BETWEEN 1 AND 160", name="ck_notification_template_title"),
        CheckConstraint("length(trim(body_template)) BETWEEN 1 AND 2000", name="ck_notification_template_body"),
        Index("ix_notification_template_lookup", "hospital_id", "template_code", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    template_code: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    content_classification: Mapped[str] = mapped_column(String(20), nullable=False, default="operational")
    title_template: Mapped[str] = mapped_column(String(160), nullable=False)
    body_template: Mapped[str] = mapped_column(String(2000), nullable=False)
    allowed_placeholders: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationIntent(Base):
    __tablename__ = "notification_intents"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "template_id"], ["notification_templates.hospital_id", "notification_templates.id"], name="fk_notification_intent_template"),
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_notification_intent_patient"),
        ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_notification_intent_consent"),
        UniqueConstraint("hospital_id", "id", name="uq_notification_intent_hospital_id"),
        UniqueConstraint("hospital_id", "idempotency_key", name="uq_notification_intent_idempotency"),
        CheckConstraint("status IN ('queued', 'processing', 'retry_scheduled', 'delivered', 'failed', 'cancelled')", name="ck_notification_intent_status"),
        CheckConstraint("channel IN ('in_app', 'email', 'sms', 'push')", name="ck_notification_intent_channel"),
        CheckConstraint("attempt_count >= 0 AND attempt_count <= max_attempts AND max_attempts BETWEEN 1 AND 8", name="ck_notification_intent_attempts"),
        CheckConstraint("(patient_id IS NULL AND consent_id IS NULL) OR (patient_id IS NOT NULL AND consent_id IS NOT NULL)", name="ck_notification_intent_patient_consent_pair"),
        CheckConstraint("length(trim(idempotency_key)) BETWEEN 8 AND 128", name="ck_notification_intent_idempotency"),
        Index("ix_notification_dispatch_queue", "hospital_id", "status", "next_attempt_at", "created_at"),
        Index("ix_notification_recipient_history", "hospital_id", "recipient_user_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    consent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    template_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    purpose: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    rendered_title: Mapped[str] = mapped_column(String(160), nullable=False)
    rendered_body: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotificationDeliveryAttempt(Base):
    __tablename__ = "notification_delivery_attempts"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "intent_id"], ["notification_intents.hospital_id", "notification_intents.id"], name="fk_notification_attempt_intent"),
        CheckConstraint("outcome IN ('accepted', 'retryable_failure', 'terminal_failure')", name="ck_notification_attempt_outcome"),
        CheckConstraint("attempt_number BETWEEN 1 AND 8", name="ck_notification_attempt_number"),
        UniqueConstraint("hospital_id", "intent_id", "attempt_number", name="uq_notification_attempt_number"),
        Index("ix_notification_attempt_history", "hospital_id", "intent_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    intent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False, default="phase3_stub")
    provider_reference: Mapped[str | None] = mapped_column(String(160))
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "intent_id"], ["notification_intents.hospital_id", "notification_intents.id"], name="fk_notification_event_intent"),
        CheckConstraint("event_type IN ('enqueued', 'dispatch_started', 'delivery_accepted', 'retry_scheduled', 'delivery_failed', 'cancelled')", name="ck_notification_event_type"),
        Index("ix_notification_event_history", "hospital_id", "intent_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    intent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
