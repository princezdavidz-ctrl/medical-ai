import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, LargeBinary,
    String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.core import TimestampMixin


class AISession(TimestampMixin, Base):
    """Private conversation container owned by one staff user in one hospital."""

    __tablename__ = "ai_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'deleted', 'expired')",
            name="ck_ai_session_status",
        ),
        CheckConstraint("message_count >= 0", name="ck_ai_session_message_count"),
        Index("ix_ai_session_owner_status", "hospital_id", "owner_user_id", "status"),
        Index("ix_ai_session_expiry", "status", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AISessionMessage(Base):
    """Encrypted conversation message; plaintext is never stored in the database."""

    __tablename__ = "ai_session_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_number", name="uq_ai_session_message_sequence"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_session_message_role"),
        CheckConstraint("sequence_number > 0", name="ck_ai_session_message_sequence"),
        CheckConstraint("length(nonce) = 12", name="ck_ai_session_message_nonce"),
        Index("ix_ai_session_message_tenant_session", "hospital_id", "session_id", "sequence_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[str] = mapped_column(String(80), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
