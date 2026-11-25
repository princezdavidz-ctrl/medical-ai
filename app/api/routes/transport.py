from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import Encounter, Hospital, HospitalMembership, Patient, PatientConsent, Role
from app.models.transport import AmbulanceVehicle, TransportEvent, TransportReceivingOffer, TransportRequest
from app.schemas.transport import (
    VehicleCreate, VehicleRead, TransportRequestCreate, TransportRequestRead,
    ReceivingBedAcceptance, VehicleAssignment, TrackingUpdate, RejectionInput,
)

router = APIRouter(prefix="/transport", tags=["ambulance and patient transport"])
_ORIGIN_STAFF = {"transfer_coordinator", "ambulance_dispatcher", "emergency_physician", "emergency_nurse", "hospital_admin"}
_FLEET_MANAGERS = {"ambulance_manager", "fleet_manager", "hospital_admin"}
_RECEIVING_STAFF = {"bed_manager", "admissions_officer", "receiving_clinician", "emergency_physician", "hospital_admin"}
_CREW_ROLES = {"ambulance_driver", "paramedic", "emergency_nurse", "ambulance_officer"}


def _role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    membership = db.scalar(select(HospitalMembership).join(
        Role, Role.id == HospitalMembership.role_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _require(db: Session, user_id: UUID, hospital_id: UUID, allowed: set[str]) -> str:
    role = _role(db, user_id, hospital_id)
    if not role or role not in allowed:
        raise HTTPException(status_code=403, detail={"code": "transport_role_not_authorized"})
    return role


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource: str, resource_id: UUID, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource, resource_id=str(resource_id), metadata=metadata or {},
    )


def _event(db: Session, origin_hospital_id: UUID, user_id: UUID, request_id: UUID, event_type: str, note=None, latitude=None, longitude=None) -> None:
    db.add(TransportEvent(
        hospital_id=origin_hospital_id, transport_request_id=request_id,
        actor_user_id=user_id, event_type=event_type, note=note,
        latitude=latitude, longitude=longitude,
    ))


def _request_by_id(db: Session, request_id: UUID, hospital_id: UUID, *, lock: bool = False):
    query = select(TransportRequest).where(
        TransportRequest.id == request_id,
        TransportRequest.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    request = db.scalar(query)
    if request is None:
        raise HTTPException(status_code=404, detail={"code": "transport_request_not_found"})
    return request



def _offer_by_id(db: Session, request_id: UUID, receiving_hospital_id: UUID, *, lock: bool = False):
    query = select(TransportReceivingOffer).where(
        TransportReceivingOffer.transport_request_id == request_id,
        TransportReceivingOffer.hospital_id == receiving_hospital_id,
    )
    if lock:
        query = query.with_for_update()
    offer = db.scalar(query)
    if offer is None:
        raise HTTPException(status_code=404, detail={"code": "receiving_transfer_offer_not_found"})
    return offer

def _active_crew(db: Session, hospital_id: UUID, user_id: UUID) -> bool:
    membership = db.scalar(select(HospitalMembership).join(
        Role, Role.id == HospitalMembership.role_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    return bool(role and role.name.strip().casefold().replace(" ", "_") in _CREW_ROLES)


@router.post("/vehicles", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: VehicleCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _FLEET_MANAGERS)
    vehicle = AmbulanceVehicle(hospital_id=hospital_id, created_by_user_id=user.id, status="available", **payload.model_dump())
    db.add(vehicle)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "transport.vehicle.created", "ambulance_vehicle", vehicle.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "vehicle_code_or_registration_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(vehicle)
    return vehicle


@router.get("/vehicles", response_model=list[VehicleRead])
def list_vehicles(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _ORIGIN_STAFF | _FLEET_MANAGERS)
    return db.scalars(select(AmbulanceVehicle).where(
        AmbulanceVehicle.hospital_id == hospital_id,
    ).order_by(AmbulanceVehicle.vehicle_code)).all()


@router.post("/requests", response_model=TransportRequestRead, status_code=status.HTTP_201_CREATED)
def create_transport_request(payload: TransportRequestCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _ORIGIN_STAFF)
    patient = db.scalar(select(Patient).where(
        Patient.id == payload.patient_id, Patient.hospital_id == hospital_id,
        Patient.status == "active",
    ))
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == payload.encounter_id, Encounter.hospital_id == hospital_id,
        Encounter.patient_id == payload.patient_id, Encounter.status == "in_progress",
    ))
    if patient is None or encounter is None:
        raise HTTPException(status_code=404, detail={"code": "active_patient_encounter_not_found"})
    consent = db.scalar(select(PatientConsent).where(
        PatientConsent.id == payload.consent_id,
        PatientConsent.hospital_id == hospital_id,
        PatientConsent.patient_id == patient.id,
        PatientConsent.purpose == "inter_hospital_transfer",
        PatientConsent.status == "granted",
        PatientConsent.basis_code.is_not(None),
        PatientConsent.granted_at.is_not(None),
        PatientConsent.granted_at <= datetime.now(timezone.utc),
        PatientConsent.withdrawn_at.is_(None),
    ))
    scope = consent.scope if consent is not None and isinstance(consent.scope, dict) else {}
    categories = scope.get("data_categories", []) if isinstance(scope, dict) else []
    permitted_uses = scope.get("permitted_uses", []) if isinstance(scope, dict) else []
    if (
        consent is None
        or (consent.expires_at is not None and consent.expires_at <= datetime.now(timezone.utc))
        or not isinstance(categories, list)
        or not isinstance(permitted_uses, list)
        or not all(isinstance(item, str) for item in categories + permitted_uses)
        or not {"identity", "clinical_summary"}.issubset(set(categories))
        or "transfer_of_care" not in permitted_uses
    ):
        raise HTTPException(status_code=403, detail={"code": "active_transfer_of_care_authorization_required"})
    if payload.transport_type == "interfacility":
        if payload.receiving_hospital_id is None or payload.receiving_hospital_id == hospital_id:
            raise HTTPException(status_code=422, detail={"code": "different_receiving_hospital_required"})
        receiving = db.scalar(select(Hospital).where(
            Hospital.id == payload.receiving_hospital_id, Hospital.status == "active",
        ))
        if receiving is None:
            raise HTTPException(status_code=404, detail={"code": "active_receiving_hospital_not_found"})
    elif payload.receiving_hospital_id is not None:
        raise HTTPException(status_code=422, detail={"code": "receiving_hospital_only_for_interfacility"})
    request = TransportRequest(
        hospital_id=hospital_id, requested_by_user_id=user.id,
        status="requested", **payload.model_dump(),
    )
    db.add(request)
    try:
        db.flush()
        if request.receiving_hospital_id is not None:
            db.add(TransportReceivingOffer(
                hospital_id=request.receiving_hospital_id, origin_hospital_id=hospital_id,
                transport_request_id=request.id, transfer_number=request.transfer_number,
                priority=request.priority, origin_description=request.origin_description,
                destination_description=request.destination_description, status="offered",
            ))
        _event(db, hospital_id, user.id, request.id, "requested")
        _audit(db, hospital_id, user.id, "transport.requested", "transport_request", request.id, {"priority": request.priority, "transport_type": request.transport_type})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "transfer_number_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.get("/requests", response_model=list[TransportRequestRead])
def list_origin_requests(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _ORIGIN_STAFF | _FLEET_MANAGERS)
    return db.scalars(select(TransportRequest).where(
        TransportRequest.hospital_id == hospital_id,
    ).order_by(TransportRequest.created_at.desc()).limit(200)).all()


@router.get("/receiving/requests")
def list_receiving_requests(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _RECEIVING_STAFF)
    rows = db.scalars(select(TransportReceivingOffer).where(
        TransportReceivingOffer.hospital_id == hospital_id,
        TransportReceivingOffer.status.in_(["offered", "bed_accepted", "arrived"]),
    ).order_by(TransportReceivingOffer.created_at.desc()).limit(200)).all()
    return [{
        "id": row.transport_request_id, "transfer_number": row.transfer_number,
        "priority": row.priority, "origin_description": row.origin_description,
        "destination_description": row.destination_description, "status": row.status,
        "bed_reference": row.bed_reference, "created_at": row.created_at,
    } for row in rows]


@router.post("/requests/{request_id}/receiving-acceptance")
def accept_receiving_bed(request_id: UUID, payload: ReceivingBedAcceptance, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, receiving_hospital_id = context
    _require(db, user.id, receiving_hospital_id, _RECEIVING_STAFF)
    offer = _offer_by_id(db, request_id, receiving_hospital_id, lock=True)
    if offer.status != "offered":
        raise HTTPException(status_code=409, detail={"code": "transfer_not_awaiting_receiving_acceptance"})
    offer.status = "bed_accepted"
    offer.accepted_by_user_id = user.id
    offer.bed_reference = payload.bed_reference
    offer.accepted_at = datetime.now(timezone.utc)
    _event(db, offer.origin_hospital_id, user.id, offer.transport_request_id, "bed_accepted", "Receiving hospital accepted the bed")
    _audit(db, receiving_hospital_id, user.id, "transport.receiving_bed_accepted", "transport_request", offer.transport_request_id)
    db.commit()
    _restore_context(db, user.id, receiving_hospital_id)
    return {"id": offer.transport_request_id, "transfer_number": offer.transfer_number, "status": offer.status, "bed_reference": offer.bed_reference}


@router.post("/requests/{request_id}/receiving-rejection")
def reject_receiving_request(request_id: UUID, payload: RejectionInput, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, receiving_hospital_id = context
    _require(db, user.id, receiving_hospital_id, _RECEIVING_STAFF)
    offer = _offer_by_id(db, request_id, receiving_hospital_id, lock=True)
    if offer.status != "offered":
        raise HTTPException(status_code=409, detail={"code": "transfer_not_awaiting_receiving_decision"})
    offer.status = "rejected"
    offer.rejected_by_user_id = user.id
    offer.rejection_reason = payload.reason
    _event(db, offer.origin_hospital_id, user.id, offer.transport_request_id, "rejected", payload.reason)
    _audit(db, receiving_hospital_id, user.id, "transport.receiving_rejected", "transport_request", offer.transport_request_id)
    db.commit()
    _restore_context(db, user.id, receiving_hospital_id)
    return {"id": offer.transport_request_id, "transfer_number": offer.transfer_number, "status": offer.status}


@router.post("/requests/{request_id}/assign-vehicle", response_model=TransportRequestRead)
def assign_vehicle(request_id: UUID, payload: VehicleAssignment, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _FLEET_MANAGERS)
    request = _request_by_id(db, request_id, hospital_id, lock=True)
    offer = db.scalar(select(TransportReceivingOffer).where(
        TransportReceivingOffer.transport_request_id == request.id,
        TransportReceivingOffer.origin_hospital_id == hospital_id,
    ).with_for_update())
    if offer is None or offer.status != "bed_accepted":
        raise HTTPException(status_code=409, detail={"code": "receiving_bed_acceptance_required"})
    request.status = "bed_accepted"
    request.receiving_accepted_by_user_id = offer.accepted_by_user_id
    request.receiving_bed_reference = offer.bed_reference
    request.receiving_accepted_at = offer.accepted_at
    vehicle = db.scalar(select(AmbulanceVehicle).where(
        AmbulanceVehicle.id == payload.vehicle_id,
        AmbulanceVehicle.hospital_id == hospital_id,
        AmbulanceVehicle.status == "available",
    ).with_for_update())
    if vehicle is None:
        raise HTTPException(status_code=409, detail={"code": "available_origin_ambulance_required"})
    if not _active_crew(db, hospital_id, payload.driver_user_id):
        raise HTTPException(status_code=422, detail={"code": "active_ambulance_driver_required"})
    if payload.crew_user_id is not None and (
        payload.crew_user_id == payload.driver_user_id or not _active_crew(db, hospital_id, payload.crew_user_id)
    ):
        raise HTTPException(status_code=422, detail={"code": "distinct_active_ambulance_crew_required"})
    vehicle.status = "assigned"
    request.assigned_vehicle_id = vehicle.id
    request.assigned_driver_user_id = payload.driver_user_id
    request.assigned_crew_user_id = payload.crew_user_id
    request.status = "vehicle_assigned"
    _event(db, hospital_id, user.id, request.id, "vehicle_assigned")
    _audit(db, hospital_id, user.id, "transport.vehicle.assigned", "transport_request", request.id, {"vehicle_id": str(vehicle.id)})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.post("/requests/{request_id}/dispatch", response_model=TransportRequestRead)
def dispatch_vehicle(request_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _FLEET_MANAGERS)
    request = _request_by_id(db, request_id, hospital_id, lock=True)
    if request.status != "vehicle_assigned":
        raise HTTPException(status_code=409, detail={"code": "assigned_vehicle_required"})
    request.status = "en_route"
    request.dispatched_by_user_id = user.id
    request.dispatched_at = datetime.now(timezone.utc)
    _event(db, hospital_id, user.id, request.id, "departed")
    _audit(db, hospital_id, user.id, "transport.dispatched", "transport_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.post("/requests/{request_id}/tracking")
def record_tracking_update(request_id: UUID, payload: TrackingUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    request = _request_by_id(db, request_id, hospital_id, lock=True)
    if request.status != "en_route" or user.id not in (request.assigned_driver_user_id, request.assigned_crew_user_id):
        raise HTTPException(status_code=403, detail={"code": "assigned_transport_crew_en_route_required"})
    if (payload.latitude is None) != (payload.longitude is None):
        raise HTTPException(status_code=422, detail={"code": "latitude_and_longitude_must_be_paired"})
    if payload.latitude is None and not payload.note:
        raise HTTPException(status_code=422, detail={"code": "tracking_update_requires_location_or_note"})
    _event(db, hospital_id, user.id, request, "location_update", payload.note, payload.latitude, payload.longitude)
    _audit(db, hospital_id, user.id, "transport.tracking.updated", "transport_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return {"request_id": request.id, "recorded": True}


@router.post("/requests/{request_id}/arrival-confirmation")
def confirm_arrival(request_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, receiving_hospital_id = context
    _require(db, user.id, receiving_hospital_id, _RECEIVING_STAFF)
    offer = _offer_by_id(db, request_id, receiving_hospital_id, lock=True)
    if offer.status != "bed_accepted":
        raise HTTPException(status_code=409, detail={"code": "accepted_transfer_not_ready_for_arrival"})
    offer.status = "arrived"
    offer.arrived_at = datetime.now(timezone.utc)
    offer.arrival_confirmed_by_user_id = user.id
    _event(db, offer.origin_hospital_id, user.id, offer.transport_request_id, "arrived")
    _audit(db, receiving_hospital_id, user.id, "transport.arrival.confirmed", "transport_request", offer.transport_request_id)
    db.commit()
    _restore_context(db, user.id, receiving_hospital_id)
    return {"id": offer.transport_request_id, "transfer_number": offer.transfer_number, "status": offer.status, "arrived_at": offer.arrived_at}


@router.post("/requests/{request_id}/release-vehicle")
def release_vehicle(request_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _FLEET_MANAGERS)
    request = _request_by_id(db, request_id, hospital_id, lock=True)
    offer = db.scalar(select(TransportReceivingOffer).where(
        TransportReceivingOffer.transport_request_id == request.id,
        TransportReceivingOffer.origin_hospital_id == hospital_id,
    ))
    if offer is None or offer.status != "arrived" or request.status != "en_route" or request.assigned_vehicle_id is None:
        raise HTTPException(status_code=409, detail={"code": "receiving_arrival_and_assigned_vehicle_required"})
    request.status = "arrived"
    request.arrived_at = offer.arrived_at
    request.arrival_confirmed_by_user_id = offer.arrival_confirmed_by_user_id
    vehicle = db.scalar(select(AmbulanceVehicle).where(
        AmbulanceVehicle.id == request.assigned_vehicle_id,
        AmbulanceVehicle.hospital_id == hospital_id,
    ).with_for_update())
    if vehicle is None or vehicle.status != "assigned":
        raise HTTPException(status_code=409, detail={"code": "assigned_vehicle_not_found"})
    vehicle.status = "available"
    _event(db, hospital_id, user.id, request, "vehicle_released", "Ambulance released back to origin fleet")
    _audit(db, hospital_id, user.id, "transport.vehicle.released", "transport_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return {"request_id": request.id, "vehicle_status": vehicle.status}



@router.post("/requests/{request_id}/cancel")
def cancel_transport_request(request_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _ORIGIN_STAFF | _FLEET_MANAGERS)
    request = _request_by_id(db, request_id, hospital_id, lock=True)
    if request.status not in ("requested", "bed_accepted", "vehicle_assigned"):
        raise HTTPException(status_code=409, detail={"code": "transport_request_not_cancellable"})
    if request.assigned_vehicle_id is not None:
        vehicle = db.scalar(select(AmbulanceVehicle).where(
            AmbulanceVehicle.id == request.assigned_vehicle_id,
            AmbulanceVehicle.hospital_id == hospital_id,
        ).with_for_update())
        if vehicle is not None and vehicle.status == "assigned":
            vehicle.status = "available"
    request.status = "cancelled"
    _event(db, hospital_id, user.id, request, "cancelled")
    _audit(db, hospital_id, user.id, "transport.cancelled", "transport_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return {"id": request.id, "transfer_number": request.transfer_number, "status": request.status}


@router.get("/requests/{request_id}/events")
def list_transport_events(request_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    if role in (_ORIGIN_STAFF | _FLEET_MANAGERS):
        request = _request_by_id(db, request_id, hospital_id)
        origin_hospital_id, transport_request_id = request.hospital_id, request.id
    elif role in _RECEIVING_STAFF:
        offer = _offer_by_id(db, request_id, hospital_id)
        origin_hospital_id, transport_request_id = offer.origin_hospital_id, offer.transport_request_id
    else:
        raise HTTPException(status_code=403, detail={"code": "transport_event_access_denied"})
    rows = db.scalars(select(TransportEvent).where(
        TransportEvent.hospital_id == origin_hospital_id,
        TransportEvent.transport_request_id == transport_request_id,
    ).order_by(TransportEvent.created_at)).all()
    return [{
        "id": row.id, "event_type": row.event_type, "actor_user_id": row.actor_user_id,
        "latitude": row.latitude, "longitude": row.longitude, "note": row.note,
        "created_at": row.created_at,
    } for row in rows]
