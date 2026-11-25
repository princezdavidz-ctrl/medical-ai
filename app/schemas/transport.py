from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class VehicleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_code: str = Field(min_length=2, max_length=80)
    registration_number: str = Field(min_length=3, max_length=40)
    vehicle_type: str = Field(pattern="^(basic_life_support|advanced_life_support|patient_transport|wheelchair|other)$")
    capacity: int = Field(default=1, ge=1, le=20)

class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    vehicle_code: str
    registration_number: str
    vehicle_type: str
    capacity: int
    status: str
    created_at: datetime

class TransportRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    encounter_id: UUID
    consent_id: UUID
    receiving_hospital_id: UUID | None = None
    transfer_number: str = Field(min_length=2, max_length=80)
    transport_type: str = Field(pattern="^interfacility$")
    priority: str = Field(default="routine", pattern="^(routine|urgent|emergency)$")
    reason: str = Field(min_length=5, max_length=3000)
    origin_description: str = Field(min_length=3, max_length=500)
    destination_description: str = Field(min_length=3, max_length=500)

class TransportRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    encounter_id: UUID
    transfer_number: str
    transport_type: str
    priority: str
    reason: str
    origin_description: str
    destination_description: str
    receiving_hospital_id: UUID | None
    status: str
    receiving_status: str | None = None
    receiving_bed_reference: str | None
    assigned_vehicle_id: UUID | None
    assigned_driver_user_id: UUID | None
    assigned_crew_user_id: UUID | None
    dispatched_at: datetime | None
    arrived_at: datetime | None
    created_at: datetime

class ReceivingBedAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bed_reference: str = Field(min_length=2, max_length=120)

class VehicleAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_id: UUID
    driver_user_id: UUID
    crew_user_id: UUID | None = None

class TrackingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    note: str | None = Field(default=None, max_length=1000)

class RejectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=1000)

class VehicleStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(available|maintenance|out_of_service)$")
