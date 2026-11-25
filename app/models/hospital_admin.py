import uuid
from datetime import datetime, time
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, Text, Time, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class HospitalAdminProfile(Base):
    __tablename__ = "hospital_admin_profiles"
    __table_args__ = (
        UniqueConstraint("hospital_id", name="uq_hospital_admin_profile_hospital"),
        UniqueConstraint("hospital_id", "id", name="uq_hospital_admin_profile_hospital_id"),
        CheckConstraint("length(country_code) = 2 AND country_code = upper(country_code)", name="ck_hospital_profile_country"),
        CheckConstraint("length(currency_code) = 3 AND currency_code = upper(currency_code)", name="ck_hospital_profile_currency"),
        CheckConstraint("facility_type IN ('general', 'specialist', 'teaching', 'referral', 'clinic', 'other')", name="ck_hospital_profile_facility_type"),
        CheckConstraint("brand_primary_color IS NULL OR brand_primary_color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_hospital_profile_primary_color"),
        CheckConstraint("brand_secondary_color IS NULL OR brand_secondary_color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_hospital_profile_secondary_color"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(32), nullable=False, default="general")
    license_number: Mapped[str | None] = mapped_column(String(120))
    address_line1: Mapped[str] = mapped_column(String(240), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(240))
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    county: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(24))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="KE")
    primary_phone: Mapped[str] = mapped_column(String(40), nullable=False)
    emergency_phone: Mapped[str | None] = mapped_column(String(40))
    administrative_email: Mapped[str] = mapped_column(String(320), nullable=False)
    website_url: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="Africa/Nairobi")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="en-KE")
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    brand_primary_color: Mapped[str | None] = mapped_column(String(7))
    brand_secondary_color: Mapped[str | None] = mapped_column(String(7))
    logo_reference: Mapped[str | None] = mapped_column(String(160))
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HospitalOperationalSettings(Base):
    __tablename__ = "hospital_operational_settings"
    __table_args__ = (
        UniqueConstraint("hospital_id", name="uq_hospital_operational_settings_hospital"),
        UniqueConstraint("hospital_id", "id", name="uq_hospital_operational_settings_hospital_id"),
        CheckConstraint("default_appointment_duration_minutes BETWEEN 5 AND 240", name="ck_hospital_settings_appointment_duration"),
        CheckConstraint("appointment_booking_advance_days BETWEEN 0 AND 365", name="ck_hospital_settings_advance_days"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    appointment_booking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    patient_self_registration_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    public_directory_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_appointment_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    appointment_booking_advance_days: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HospitalOperatingHour(Base):
    __tablename__ = "hospital_operating_hours"
    __table_args__ = (
        UniqueConstraint("hospital_id", "day_of_week", name="uq_hospital_operating_hours_day"),
        UniqueConstraint("hospital_id", "id", name="uq_hospital_operating_hours_hospital_id"),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_hospital_operating_day"),
        CheckConstraint("(is_closed = true AND opens_at IS NULL AND closes_at IS NULL) OR (is_closed = false AND opens_at IS NOT NULL AND closes_at IS NOT NULL AND opens_at < closes_at)", name="ck_hospital_operating_time"),
        Index("ix_hospital_operating_hours_day", "hospital_id", "day_of_week"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opens_at: Mapped[time | None] = mapped_column(Time)
    closes_at: Mapped[time | None] = mapped_column(Time)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HospitalAdminEvent(Base):
    __tablename__ = "hospital_admin_events"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_hospital_admin_event_hospital_id"),
        CheckConstraint("event_type IN ('profile_created', 'profile_updated', 'settings_updated', 'operating_hours_updated', 'department_created', 'department_updated', 'department_deactivated')", name="ck_hospital_admin_event_type"),
        Index("ix_hospital_admin_event_history", "hospital_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
