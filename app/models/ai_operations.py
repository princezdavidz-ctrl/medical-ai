import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIHospitalControl(Base):
    """Hospital-scoped emergency pause for central AI execution."""

    __tablename__ = "ai_hospital_controls"

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("hospitals.id"), primary_key=True
    )
    ai_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pause_reason: Mapped[str | None] = mapped_column(Text)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
