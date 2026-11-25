from datetime import time, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class HospitalProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    legal_name: str = Field(min_length=2, max_length=240)
    display_name: str = Field(min_length=2, max_length=240)
    facility_type: str = Field(pattern="^(general|specialist|teaching|referral|clinic|other)$")
    license_number: str | None = Field(default=None, max_length=120)
    address_line1: str = Field(min_length=3, max_length=240)
    address_line2: str | None = Field(default=None, max_length=240)
    city: str = Field(min_length=2, max_length=120)
    county: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=24)
    country_code: str = Field(default="KE", pattern="^[A-Z]{2}$")
    primary_phone: str = Field(min_length=5, max_length=40)
    emergency_phone: str | None = Field(default=None, max_length=40)
    administrative_email: str = Field(min_length=5, max_length=320)
    website_url: str | None = Field(default=None, pattern="^https?://[^ ]+$", max_length=500)
    timezone: str = Field(default="Africa/Nairobi", min_length=3, max_length=80)
    locale: str = Field(default="en-KE", pattern="^[a-z]{2}(-[A-Z]{2})?$")
    currency_code: str = Field(default="KES", pattern="^[A-Z]{3}$")
    brand_primary_color: str | None = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")
    brand_secondary_color: str | None = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")
    logo_reference: str | None = Field(default=None, pattern="^vault://[0-9a-fA-F-]{36}$")


class HospitalProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    legal_name: str
    display_name: str
    facility_type: str
    license_number: str | None
    address_line1: str
    address_line2: str | None
    city: str
    county: str | None
    postal_code: str | None
    country_code: str
    primary_phone: str
    emergency_phone: str | None
    administrative_email: str
    website_url: str | None
    timezone: str
    locale: str
    currency_code: str
    brand_primary_color: str | None
    brand_secondary_color: str | None
    logo_reference: str | None
    updated_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class HospitalOperationalSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    appointment_booking_enabled: bool = True
    patient_self_registration_enabled: bool = True
    public_directory_enabled: bool = False
    default_appointment_duration_minutes: int = Field(default=20, ge=5, le=240)
    appointment_booking_advance_days: int = Field(default=60, ge=0, le=365)


class HospitalOperationalSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID | None = None
    hospital_id: UUID
    appointment_booking_enabled: bool
    patient_self_registration_enabled: bool
    public_directory_enabled: bool
    default_appointment_duration_minutes: int
    appointment_booking_advance_days: int
    updated_by_user_id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OperatingHourInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day_of_week: int = Field(ge=0, le=6)
    is_closed: bool = False
    opens_at: time | None = None
    closes_at: time | None = None


class OperatingHoursReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: list[OperatingHourInput] = Field(min_length=7, max_length=7)


class OperatingHourRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    day_of_week: int
    is_closed: bool
    opens_at: time | None
    closes_at: time | None
    updated_by_user_id: UUID
    updated_at: datetime


class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=40, pattern="^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=4000)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=40)
    manager_user_id: UUID | None = None
    parent_department_id: UUID | None = None


class DepartmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=160)
    code: str | None = Field(default=None, min_length=2, max_length=40, pattern="^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=4000)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=40)
    manager_user_id: UUID | None = None
    parent_department_id: UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    name: str
    code: str
    description: str | None
    contact_email: str | None
    contact_phone: str | None
    manager_user_id: UUID | None
    parent_department_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime
