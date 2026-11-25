import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AmbulanceVehicle(Base):
    __tablename__ = "ambulance_vehicles"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_ambulance_vehicle_hospital_id"),
        UniqueConstraint("hospital_id", "vehicle_code", name="uq_ambulance_vehicle_code"),
        UniqueConstraint("hospital_id", "registration_number", name="uq_ambulance_vehicle_registration"),
        CheckConstraint("vehicle_type IN ('basic_life_support', 'advanced_life_support', 'patient_transport', 'wheelchair', 'other')", name="ck_ambulance_vehicle_type"),
        CheckConstraint("status IN ('available', 'assigned', 'maintenance', 'out_of_service')", name="ck_ambulance_vehicle_status"),
        CheckConstraint("capacity >= 1 AND capacity <= 20", name="ck_ambulance_vehicle_capacity"),
        Index("ix_ambulance_vehicle_status", "hospital_id", "status", "vehicle_type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    vehicle_code: Mapped[str] = mapped_column(String(80), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(40), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(32), nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="available")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TransportRequest(Base):
    __tablename__ = "transport_requests"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_transport_request_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_transport_request_encounter_patient"),
        ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_transport_request_consent"),
        ForeignKeyConstraint(["hospital_id", "assigned_vehicle_id"], ["ambulance_vehicles.hospital_id", "ambulance_vehicles.id"], name="fk_transport_request_vehicle"),
        UniqueConstraint("hospital_id", "id", name="uq_transport_request_hospital_id"),
        UniqueConstraint("hospital_id", "transfer_number", name="uq_transport_request_number"),
        CheckConstraint("transport_type IN ('interfacility', 'emergency', 'scheduled', 'internal')", name="ck_transport_request_type"),
        CheckConstraint("priority IN ('routine', 'urgent', 'emergency')", name="ck_transport_request_priority"),
        CheckConstraint("status IN ('requested', 'accepted', 'bed_accepted', 'vehicle_assigned', 'en_route', 'arrived', 'rejected', 'cancelled')", name="ck_transport_request_status"),
        CheckConstraint("length(trim(origin_description)) >= 3 AND length(trim(destination_description)) >= 3", name="ck_transport_request_locations"),
        CheckConstraint("transport_type != 'interfacility' OR (receiving_hospital_id IS NOT NULL AND receiving_hospital_id != hospital_id)", name="ck_transport_interfacility_destination"),
        CheckConstraint("status NOT IN ('bed_accepted', 'vehicle_assigned', 'en_route', 'arrived') OR (receiving_accepted_by_user_id IS NOT NULL AND receiving_bed_reference IS NOT NULL)", name="ck_transport_bed_acceptance_state"),
        CheckConstraint("status NOT IN ('vehicle_assigned', 'en_route', 'arrived') OR (assigned_vehicle_id IS NOT NULL AND assigned_driver_user_id IS NOT NULL)", name="ck_transport_vehicle_assignment_state"),
        CheckConstraint("status != 'arrived' OR arrived_at IS NOT NULL", name="ck_transport_arrival_state"),
        Index("ix_transport_request_queue", "hospital_id", "status", "priority", "created_at"),
        Index("ix_transport_request_destination", "receiving_hospital_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    consent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    receiving_hospital_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hospitals.id"))
    transfer_number: Mapped[str] = mapped_column(String(80), nullable=False)
    transport_type: Mapped[str] = mapped_column(String(24), nullable=False)
    priority: Mapped[str] = mapped_column(String(24), nullable=False, default="routine")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    origin_description: Mapped[str] = mapped_column(String(500), nullable=False)
    destination_description: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="requested")
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    receiving_accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    receiving_bed_reference: Mapped[str | None] = mapped_column(String(120))
    receiving_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_vehicle_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    assigned_driver_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    assigned_crew_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    dispatched_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrival_confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    rejected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TransportEvent(Base):
    __tablename__ = "transport_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "transport_request_id"], ["transport_requests.hospital_id", "transport_requests.id"], name="fk_transport_event_request"),
        UniqueConstraint("hospital_id", "id", name="uq_transport_event_hospital_id"),
        CheckConstraint("event_type IN ('requested', 'accepted', 'bed_accepted', 'vehicle_assigned', 'departed', 'location_update', 'arrived', 'rejected', 'cancelled')", name="ck_transport_event_type"),
        CheckConstraint("(latitude IS NULL AND longitude IS NULL) OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)", name="ck_transport_event_coordinates"),
        Index("ix_transport_event_request_time", "hospital_id", "transport_request_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    transport_request_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    latitude: Mapped[float | None] = mapped_column()
    longitude: Mapped[float | None] = mapped_column()
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
