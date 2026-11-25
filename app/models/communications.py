import uuid
from datetime import datetime, time as time_type

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, String, Text, Time, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("hospital_id", "user_id", name="uq_notification_preference_user"),
        CheckConstraint("json_typeof(muted_categories) = 'array'", name="ck_notification_muted_categories"),
        CheckConstraint("(quiet_hours_start IS NULL AND quiet_hours_end IS NULL) OR (quiet_hours_start IS NOT NULL AND quiet_hours_end IS NOT NULL)", name="ck_notification_quiet_hours_pair"),
        Index("ix_notification_preferences_user", "hospital_id", "user_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    muted_categories: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    quiet_hours_start: Mapped[time_type | None] = mapped_column(Time)
    quiet_hours_end: Mapped[datetime | None] = mapped_column(Time)
    timezone_name: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HospitalNotification(Base):
    __tablename__ = "hospital_notifications"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_notification_patient"),
        ForeignKeyConstraint(["hospital_id", "portal_link_id", "patient_id", "recipient_user_id"], ["patient_portal_links.hospital_id", "patient_portal_links.id", "patient_portal_links.patient_id", "patient_portal_links.portal_user_id"], name="fk_notification_patient_portal_link"),
        UniqueConstraint("hospital_id", "id", "recipient_user_id", name="uq_notification_hospital_id_recipient"),
        UniqueConstraint("hospital_id", "idempotency_key", name="uq_notification_idempotency"),
        CheckConstraint("recipient_type IN ('patient', 'staff')", name="ck_notification_recipient_type"),
        CheckConstraint("category IN ('appointment', 'clinical_update', 'laboratory', 'radiology', 'medication', 'billing', 'insurance', 'records', 'telemedicine', 'transfer', 'staff_schedule', 'security', 'system', 'message', 'other')", name="ck_notification_category"),
        CheckConstraint("priority IN ('normal', 'high', 'urgent', 'critical')", name="ck_notification_priority"),
        CheckConstraint("status IN ('queued', 'partially_delivered', 'delivered', 'failed', 'cancelled')", name="ck_notification_status"),
        CheckConstraint("json_typeof(channels) = 'array' AND json_array_length(channels) > 0", name="ck_notification_channels"),
        CheckConstraint("NOT contains_sensitive_data OR (json_array_length(channels) = 1 AND channels->>0 = 'in_app')", name="ck_notification_sensitive_in_app_only"),
        CheckConstraint("(recipient_type = 'patient' AND patient_id IS NOT NULL AND portal_link_id IS NOT NULL) OR (recipient_type = 'staff' AND patient_id IS NULL AND portal_link_id IS NULL)", name="ck_notification_patient_recipient_link"),
        CheckConstraint("(read_at IS NULL AND read_by_user_id IS NULL) OR (read_at IS NOT NULL AND read_by_user_id = recipient_user_id)", name="ck_notification_read_state"),
        CheckConstraint("(status = 'cancelled' AND cancelled_at IS NOT NULL AND cancelled_by_user_id IS NOT NULL) OR (status != 'cancelled' AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL)", name="ck_notification_cancel_state"),
        Index("ix_notification_recipient_inbox", "hospital_id", "recipient_user_id", "status", "created_at"),
        Index("ix_notification_category_queue", "hospital_id", "category", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(12), nullable=False)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    portal_link_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(500))
    channels: Mapped[list] = mapped_column(JSON, nullable=False)
    contains_sensitive_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "notification_id", "recipient_user_id"], ["hospital_notifications.hospital_id", "hospital_notifications.id", "hospital_notifications.recipient_user_id"], name="fk_notification_delivery_notification"),
        UniqueConstraint("hospital_id", "notification_id", "channel", name="uq_notification_delivery_channel"),
        CheckConstraint("channel IN ('in_app', 'email', 'sms')", name="ck_notification_delivery_channel"),
        CheckConstraint("status IN ('pending', 'processing', 'sent', 'delivered', 'failed', 'cancelled')", name="ck_notification_delivery_status"),
        CheckConstraint("attempts >= 0", name="ck_notification_delivery_attempts"),
        Index("ix_notification_delivery_queue", "hospital_id", "status", "next_attempt_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    notification_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(1000))
    provider_message_id: Mapped[str | None] = mapped_column(String(180))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "notification_id", "recipient_user_id"], ["hospital_notifications.hospital_id", "hospital_notifications.id", "hospital_notifications.recipient_user_id"], name="fk_notification_outbox_notification"),
        UniqueConstraint("hospital_id", "idempotency_key", name="uq_notification_outbox_idempotency"),
        CheckConstraint("status IN ('pending', 'processing', 'published', 'failed', 'cancelled')", name="ck_notification_outbox_status"),
        CheckConstraint("attempts >= 0", name="ck_notification_outbox_attempts"),
        Index("ix_notification_outbox_claim", "status", "available_at", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    notification_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, default="notification.dispatch_requested")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(120))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommunicationThread(Base):
    __tablename__ = "communication_threads"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_communication_thread_patient"),
        ForeignKeyConstraint(["hospital_id", "portal_link_id", "patient_id", "patient_user_id"], ["patient_portal_links.hospital_id", "patient_portal_links.id", "patient_portal_links.patient_id", "patient_portal_links.portal_user_id"], name="fk_communication_thread_portal_link"),
        ForeignKeyConstraint(["hospital_id", "assigned_staff_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_communication_thread_assigned_staff"),
        UniqueConstraint("hospital_id", "id", "patient_id", "portal_link_id", "patient_user_id", "assigned_staff_user_id", name="uq_communication_thread_participants"),
        CheckConstraint("category IN ('care_question', 'appointment', 'billing', 'records', 'technical_support', 'other')", name="ck_communication_thread_category"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_communication_thread_status"),
        CheckConstraint("length(trim(subject)) >= 2", name="ck_communication_thread_subject"),
        CheckConstraint("(status = 'open' AND closed_by_user_id IS NULL AND closed_at IS NULL AND close_reason IS NULL) OR (status = 'closed' AND closed_by_user_id IS NOT NULL AND closed_at IS NOT NULL AND close_reason IS NOT NULL)", name="ck_communication_thread_close_state"),
        Index("ix_communication_thread_staff", "hospital_id", "assigned_staff_user_id", "status", "last_message_at"),
        Index("ix_communication_thread_patient", "hospital_id", "patient_user_id", "status", "last_message_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    portal_link_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    patient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_staff_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    subject: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[str | None] = mapped_column(String(1000))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CommunicationMessage(Base):
    __tablename__ = "communication_messages"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "thread_id", "patient_id", "portal_link_id", "patient_user_id", "assigned_staff_user_id"], ["communication_threads.hospital_id", "communication_threads.id", "communication_threads.patient_id", "communication_threads.portal_link_id", "communication_threads.patient_user_id", "communication_threads.assigned_staff_user_id"], name="fk_communication_message_thread"),
        UniqueConstraint("hospital_id", "id", "thread_id", "patient_id", name="uq_communication_message_thread_patient"),
        CheckConstraint("sender_type IN ('patient', 'staff')", name="ck_communication_message_sender_type"),
        CheckConstraint("(sender_type = 'patient' AND sender_user_id = patient_user_id) OR (sender_type = 'staff' AND sender_user_id = assigned_staff_user_id)", name="ck_communication_message_sender_identity"),
        CheckConstraint("length(trim(body)) >= 1 AND length(body) <= 5000", name="ck_communication_message_body"),
        Index("ix_communication_message_thread", "hospital_id", "thread_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    portal_link_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    patient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_staff_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sender_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(12), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommunicationMessageReceipt(Base):
    __tablename__ = "communication_message_receipts"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "message_id", "thread_id", "patient_id"], ["communication_messages.hospital_id", "communication_messages.id", "communication_messages.thread_id", "communication_messages.patient_id"], name="fk_communication_receipt_message"),
        UniqueConstraint("hospital_id", "message_id", "reader_user_id", name="uq_communication_message_reader"),
        CheckConstraint("read_at IS NOT NULL", name="ck_communication_receipt_read_at"),
        Index("ix_communication_receipt_thread", "hospital_id", "thread_id", "reader_user_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reader_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommunicationEvent(Base):
    __tablename__ = "communication_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "thread_id", "patient_id"], ["communication_threads.hospital_id", "communication_threads.id", "communication_threads.patient_id"], name="fk_communication_event_thread"),
        UniqueConstraint("hospital_id", "id", name="uq_communication_event_hospital_id"),
        CheckConstraint("event_type IN ('thread_opened', 'message_sent', 'message_read', 'thread_closed')", name="ck_communication_event_type"),
        Index("ix_communication_event_thread", "hospital_id", "thread_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
