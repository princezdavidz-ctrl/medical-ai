from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, EmailStr, HttpUrl

class HospitalSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address: str | None = Field(default=None, max_length=2000)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    website_url: HttpUrl | None = None
    timezone_name: str = Field(default="Africa/Nairobi", min_length=3, max_length=80)
    locale: str = Field(default="en-KE", min_length=2, max_length=20)
    currency_code: str = Field(default="KES", pattern="^[A-Z]{3}$")
    country_code: str = Field(default="KE", pattern="^[A-Z]{2}$")

class HospitalSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    address: str | None
    contact_email: str | None
    contact_phone: str | None
    website_url: str | None
    timezone_name: str
    locale: str
    currency_code: str
    country_code: str
    updated_by_user_id: UUID
    updated_at: datetime

class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=40, pattern="^[A-Za-z0-9_-]+$")

class DepartmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    status: str = Field(pattern="^(active|inactive)$")

class RoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80, pattern="^[a-z][a-z0-9_]*$")
    description: str | None = Field(default=None, max_length=1000)

class MembershipDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern="^(activate|reject|suspend)$")
    role_id: UUID | None = None
    department_id: UUID | None = None
