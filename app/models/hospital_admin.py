import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class HospitalAdminSettings(Base):
    __tablename__ = "hospital_admin_settings"
    __table_args__ = (
        UniqueConstraint("hospital_id", name="uq_hospital_admin_settings_hospital"),
        CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="ck_hospital_admin_currency"),
        CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="ck_hospital_admin_country"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    website_url: Mapped[str | None] = mapped_column(String(500))
    timezone_name: Mapped[str] = mapped_column(String(80), nullable=False, default="Africa/Nairobi")
    locale: Mapped[str] = mapped_column(String(20), nullable=False, default="en-KE")
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="KE")
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
