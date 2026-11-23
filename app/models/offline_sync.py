import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text,
    UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.core import TimestampMixin


class OfflineKnowledgeInstallation(TimestampMixin, Base):
    """Hospital-specific record of a verified, installed offline knowledge snapshot."""

    __tablename__ = "offline_knowledge_installations"
    __table_args__ = (
        UniqueConstraint("hospital_id", "package_id", name="uq_offline_install_hospital_package"),
        CheckConstraint(
            "status IN ('verified', 'installed', 'stale', 'revoked', 'failed')",
            name="ck_offline_install_status",
        ),
        CheckConstraint("length(payload_sha256) = 64", name="ck_offline_install_digest_length"),
        Index("ix_offline_install_hospital_status", "hospital_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    package_id: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_version: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signing_key_id: Mapped[str] = mapped_column(String(160), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(80), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    encrypted_storage_ref: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="verified")


class OfflineSyncCursor(TimestampMixin, Base):
    """Per-hospital, per-source stream cursor advanced only after durable application."""

    __tablename__ = "offline_sync_cursors"
    __table_args__ = (
        UniqueConstraint(
            "hospital_id", "source_node_id", "stream_name",
            name="uq_offline_sync_cursor_stream",
        ),
        Index("ix_offline_sync_cursor_hospital", "hospital_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    source_node_id: Mapped[str] = mapped_column(String(160), nullable=False)
    stream_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_sequence: Mapped[int] = mapped_column(default=0, nullable=False)
    last_event_id: Mapped[str | None] = mapped_column(String(160))


class OfflineSyncEvent(Base):
    """Metadata-only inbound event record; clinical payloads remain in encrypted storage."""

    __tablename__ = "offline_sync_events"
    __table_args__ = (
        UniqueConstraint(
            "hospital_id", "source_node_id", "stream_name", "event_id",
            name="uq_offline_sync_event_identity",
        ),
        UniqueConstraint(
            "hospital_id", "source_node_id", "stream_name", "sequence_number",
            name="uq_offline_sync_event_sequence",
        ),
        CheckConstraint(
            "status IN ('queued', 'conflict', 'applied', 'acknowledged', 'rejected')",
            name="ck_offline_sync_event_status",
        ),
        CheckConstraint("sequence_number > 0", name="ck_offline_sync_event_sequence_positive"),
        CheckConstraint("length(payload_sha256) = 64", name="ck_offline_sync_event_digest_length"),
        Index("ix_offline_sync_event_pending", "hospital_id", "status", "sequence_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    source_node_id: Mapped[str] = mapped_column(String(160), nullable=False)
    stream_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_storage_ref: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OfflineSyncConflict(Base):
    """Explicitly tracked gaps, sequence collisions and digest mismatches."""

    __tablename__ = "offline_sync_conflicts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'resolved', 'rejected')",
            name="ck_offline_sync_conflict_status",
        ),
        Index("ix_offline_sync_conflict_hospital_status", "hospital_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offline_sync_events.id"), nullable=False)
    conflict_code: Mapped[str] = mapped_column(String(100), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OfflineDeliveryOutbox(TimestampMixin, Base):
    """Durable outbound delivery metadata with idempotency and explicit partner ack."""

    __tablename__ = "offline_delivery_outbox"
    __table_args__ = (
        UniqueConstraint(
            "hospital_id", "destination_node_id", "idempotency_key",
            name="uq_offline_outbox_idempotency",
        ),
        CheckConstraint(
            "status IN ('queued', 'sending', 'delivered', 'failed', 'cancelled')",
            name="ck_offline_outbox_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_offline_outbox_attempt_count"),
        CheckConstraint("length(payload_sha256) = 64", name="ck_offline_outbox_digest_length"),
        Index("ix_offline_outbox_dispatch", "hospital_id", "status", "next_attempt_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    destination_node_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_storage_ref: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(120))
    partner_ack_reference: Mapped[str | None] = mapped_column(String(240))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
