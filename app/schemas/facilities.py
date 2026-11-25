from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class LocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_location_id: UUID | None = None
    location_code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    location_type: str = Field(pattern="^(campus|building|floor|wing|department|room|utility_area|external_area)$")
    building: str | None = Field(default=None, max_length=120)
    floor: str | None = Field(default=None, max_length=40)
    room_number: str | None = Field(default=None, max_length=40)

class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    parent_location_id: UUID | None
    location_code: str
    name: str
    location_type: str
    building: str | None
    floor: str | None
    room_number: str | None
    status: str
    created_at: datetime

class LocationStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(active|inactive|closed)$")

class WorkOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_order_number: str = Field(min_length=2, max_length=80)
    facility_location_id: UUID
    asset_record_id: UUID | None = None
    category: str = Field(pattern="^(electrical|plumbing|hvac|building|medical_equipment|safety|other)$")
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    description: str = Field(min_length=5, max_length=5000)

class WorkOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    work_order_number: str
    facility_location_id: UUID
    asset_record_id: UUID | None
    category: str
    priority: str
    description: str
    status: str
    requested_by_user_id: UUID
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    assigned_to_user_id: UUID | None
    assigned_by_user_id: UUID | None
    assigned_at: datetime | None
    completed_by_user_id: UUID | None
    completed_at: datetime | None
    completion_note: str | None
    created_at: datetime

class WorkOrderAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_to_user_id: UUID

class WorkOrderCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completion_note: str = Field(min_length=5, max_length=5000)
