from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import HospitalMembership, Role
from app.models.facilities import FacilityLocation, MaintenanceEvent, MaintenanceWorkOrder
from app.models.inventory import AssetRecord

from app.schemas.facilities import (
    LocationCreate, LocationRead, LocationStatusUpdate,
    WorkOrderCreate, WorkOrderRead, WorkOrderAssignment, WorkOrderCompletion,
)

router = APIRouter(prefix="/facilities", tags=["facilities and maintenance"])
_FACILITIES = {"facilities_officer", "facilities_manager", "maintenance_technician", "biomedical_engineer", "hospital_admin"}
_MANAGERS = {"facilities_manager", "hospital_admin"}
_TECHNICIANS = {"maintenance_technician", "biomedical_engineer", "facilities_manager", "hospital_admin"}


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
        raise HTTPException(status_code=403, detail={"code": "facilities_role_not_authorized"})
    return role


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource: str, resource_id: UUID, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource, resource_id=str(resource_id), metadata=metadata or {},
    )


def _event(db: Session, hospital_id: UUID, user_id: UUID, order_id: UUID, event_type: str, note: str | None = None) -> None:
    db.add(MaintenanceEvent(
        hospital_id=hospital_id, work_order_id=order_id,
        actor_user_id=user_id, event_type=event_type, note=note,
    ))


@router.post("/locations", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
def create_location(payload: LocationCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MANAGERS)
    if payload.parent_location_id:
        parent = db.scalar(select(FacilityLocation).where(
            FacilityLocation.id == payload.parent_location_id,
            FacilityLocation.hospital_id == hospital_id,
            FacilityLocation.status == "active",
        ))
        if parent is None:
            raise HTTPException(status_code=404, detail={"code": "active_parent_location_not_found"})
    location = FacilityLocation(
        hospital_id=hospital_id, created_by_user_id=user.id, status="active",
        **payload.model_dump(),
    )
    db.add(location)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "facilities.location.created", "facility_location", location.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "location_code_or_parent_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(location)
    return location


@router.get("/locations", response_model=list[LocationRead])
def list_locations(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _FACILITIES | _MANAGERS)
    return db.scalars(select(FacilityLocation).where(
        FacilityLocation.hospital_id == hospital_id,
    ).order_by(FacilityLocation.location_code)).all()


@router.patch("/locations/{location_id}/status", response_model=LocationRead)
def update_location_status(location_id: UUID, payload: LocationStatusUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MANAGERS)
    location = db.scalar(select(FacilityLocation).where(
        FacilityLocation.id == location_id, FacilityLocation.hospital_id == hospital_id,
    ).with_for_update())
    if location is None:
        raise HTTPException(status_code=404, detail={"code": "facility_location_not_found"})
    if location.status == "closed" and payload.status != "closed":
        raise HTTPException(status_code=409, detail={"code": "closed_location_is_terminal"})
    if payload.status in ("inactive", "closed"):
        active_child = db.scalar(select(FacilityLocation.id).where(
            FacilityLocation.hospital_id == hospital_id,
            FacilityLocation.parent_location_id == location.id,
            FacilityLocation.status == "active",
        ).limit(1))
        if active_child:
            raise HTTPException(status_code=409, detail={"code": "active_child_locations_exist"})
        open_order = db.scalar(select(MaintenanceWorkOrder.id).where(
            MaintenanceWorkOrder.hospital_id == hospital_id,
            MaintenanceWorkOrder.facility_location_id == location.id,
            MaintenanceWorkOrder.status.in_(["requested", "approved", "assigned", "in_progress"]),
        ).limit(1))
        if open_order:
            raise HTTPException(status_code=409, detail={"code": "open_maintenance_orders_exist"})
    location.status = payload.status
    _audit(db, hospital_id, user.id, "facilities.location.status_changed", "facility_location", location.id, {"status": payload.status})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(location)
    return location


@router.post("/work-orders", response_model=WorkOrderRead, status_code=status.HTTP_201_CREATED)
def create_work_order(payload: WorkOrderCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _FACILITIES | _MANAGERS)
    location = db.scalar(select(FacilityLocation).where(
        FacilityLocation.id == payload.facility_location_id,
        FacilityLocation.hospital_id == hospital_id,
        FacilityLocation.status == "active",
    ))
    if location is None:
        raise HTTPException(status_code=404, detail={"code": "active_facility_location_not_found"})
    if payload.asset_record_id:
        asset = db.scalar(select(AssetRecord).where(
            AssetRecord.id == payload.asset_record_id, AssetRecord.hospital_id == hospital_id,
            AssetRecord.status.in_(["in_service", "under_maintenance"]),
        ))
        if asset is None:
            raise HTTPException(status_code=404, detail={"code": "active_asset_not_found"})
    order = MaintenanceWorkOrder(
        hospital_id=hospital_id, requested_by_user_id=user.id,
        status="requested", **payload.model_dump(),
    )
    db.add(order)
    try:
        db.flush()
        _event(db, hospital_id, user.id, order.id, "requested")
        _audit(db, hospital_id, user.id, "facilities.work_order.requested", "maintenance_work_order", order.id, {"priority": order.priority, "category": order.category})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "work_order_number_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(order)
    return order


@router.get("/work-orders", response_model=list[WorkOrderRead])
def list_work_orders(status_filter: str | None = None, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _FACILITIES | _MANAGERS)
    query = select(MaintenanceWorkOrder).where(MaintenanceWorkOrder.hospital_id == hospital_id)
    if status_filter:
        allowed = {"requested", "approved", "assigned", "in_progress", "completed", "rejected", "cancelled"}
        if status_filter not in allowed:
            raise HTTPException(status_code=422, detail={"code": "invalid_work_order_status_filter"})
        query = query.where(MaintenanceWorkOrder.status == status_filter)
    return db.scalars(query.order_by(MaintenanceWorkOrder.created_at.desc()).limit(500)).all()


@router.post("/work-orders/{order_id}/approve", response_model=WorkOrderRead)
def approve_work_order(order_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MANAGERS)
    order = db.scalar(select(MaintenanceWorkOrder).where(
        MaintenanceWorkOrder.id == order_id, MaintenanceWorkOrder.hospital_id == hospital_id,
    ).with_for_update())
    if order is None or order.status != "requested":
        raise HTTPException(status_code=404, detail={"code": "requested_work_order_not_found"})
    if order.requested_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_work_order_approval_required"})
    order.status, order.approved_by_user_id, order.approved_at = "approved", user.id, datetime.now(timezone.utc)
    _event(db, hospital_id, user.id, order.id, "approved")
    _audit(db, hospital_id, user.id, "facilities.work_order.approved", "maintenance_work_order", order.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(order)
    return order


@router.post("/work-orders/{order_id}/assign", response_model=WorkOrderRead)
def assign_work_order(order_id: UUID, payload: WorkOrderAssignment, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MANAGERS)
    order = db.scalar(select(MaintenanceWorkOrder).where(
        MaintenanceWorkOrder.id == order_id, MaintenanceWorkOrder.hospital_id == hospital_id,
    ).with_for_update())
    if order is None or order.status not in ("approved", "assigned"):
        raise HTTPException(status_code=409, detail={"code": "approved_work_order_required"})
    membership = db.scalar(select(HospitalMembership).join(
        Role, Role.id == HospitalMembership.role_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == payload.assigned_to_user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    role_name = role.name.strip().casefold().replace(" ", "_") if role else ""
    if role_name not in _TECHNICIANS:
        raise HTTPException(status_code=422, detail={"code": "active_maintenance_technician_required"})
    order.assigned_to_user_id = payload.assigned_to_user_id
    order.assigned_by_user_id = user.id
    order.assigned_at = datetime.now(timezone.utc)
    order.status = "assigned"
    _event(db, hospital_id, user.id, order.id, "assigned", "Assigned maintenance work order")
    _audit(db, hospital_id, user.id, "facilities.work_order.assigned", "maintenance_work_order", order.id, {"assigned_to_user_id": str(payload.assigned_to_user_id)})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(order)
    return order


@router.post("/work-orders/{order_id}/start", response_model=WorkOrderRead)
def start_work_order(order_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _TECHNICIANS)
    order = db.scalar(select(MaintenanceWorkOrder).where(
        MaintenanceWorkOrder.id == order_id, MaintenanceWorkOrder.hospital_id == hospital_id,
    ).with_for_update())
    if order is None or order.status != "assigned" or order.assigned_to_user_id != user.id:
        raise HTTPException(status_code=409, detail={"code": "assigned_work_order_required"})
    order.status = "in_progress"
    _event(db, hospital_id, user.id, order.id, "started")
    _audit(db, hospital_id, user.id, "facilities.work_order.started", "maintenance_work_order", order.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(order)
    return order


@router.post("/work-orders/{order_id}/complete", response_model=WorkOrderRead)
def complete_work_order(order_id: UUID, payload: WorkOrderCompletion, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require(db, user.id, hospital_id, _TECHNICIANS)
    order = db.scalar(select(MaintenanceWorkOrder).where(
        MaintenanceWorkOrder.id == order_id, MaintenanceWorkOrder.hospital_id == hospital_id,
    ).with_for_update())
    if order is None or order.status != "in_progress":
        raise HTTPException(status_code=409, detail={"code": "in_progress_work_order_required"})
    if order.assigned_to_user_id != user.id and role not in _MANAGERS:
        raise HTTPException(status_code=403, detail={"code": "assigned_technician_required"})
    order.status, order.completed_by_user_id = "completed", user.id
    order.completed_at, order.completion_note = datetime.now(timezone.utc), payload.completion_note
    _event(db, hospital_id, user.id, order.id, "completed", payload.completion_note)
    _audit(db, hospital_id, user.id, "facilities.work_order.completed", "maintenance_work_order", order.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(order)
    return order


@router.post("/work-orders/{order_id}/reject", response_model=WorkOrderRead)
def reject_work_order(order_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MANAGERS)
    order = db.scalar(select(MaintenanceWorkOrder).where(
        MaintenanceWorkOrder.id == order_id, MaintenanceWorkOrder.hospital_id == hospital_id,
    ).with_for_update())
    if order is None or order.status != "requested":
        raise HTTPException(status_code=409, detail={"code": "requested_work_order_required"})
    if order.requested_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_work_order_decision_required"})
    order.status = "rejected"
    _event(db, hospital_id, user.id, order.id, "rejected")
    _audit(db, hospital_id, user.id, "facilities.work_order.rejected", "maintenance_work_order", order.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(order)
    return order


@router.post("/work-orders/{order_id}/cancel", response_model=WorkOrderRead)
def cancel_work_order(order_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MANAGERS)
    order = db.scalar(select(MaintenanceWorkOrder).where(
        MaintenanceWorkOrder.id == order_id, MaintenanceWorkOrder.hospital_id == hospital_id,
    ).with_for_update())
    if order is None or order.status not in ("requested", "approved", "assigned"):
        raise HTTPException(status_code=409, detail={"code": "cancellable_work_order_required"})
    order.status = "cancelled"
    _event(db, hospital_id, user.id, order.id, "cancelled")
    _audit(db, hospital_id, user.id, "facilities.work_order.cancelled", "maintenance_work_order", order.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(order)
    return order


@router.get("/work-orders/{order_id}/events")
def list_work_order_events(order_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _FACILITIES | _MANAGERS)
    order = db.scalar(select(MaintenanceWorkOrder.id).where(
        MaintenanceWorkOrder.id == order_id, MaintenanceWorkOrder.hospital_id == hospital_id,
    ))
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "work_order_not_found"})
    events = db.scalars(select(MaintenanceEvent).where(
        MaintenanceEvent.hospital_id == hospital_id,
        MaintenanceEvent.work_order_id == order_id,
    ).order_by(MaintenanceEvent.created_at)).all()
    return [{"id": e.id, "event_type": e.event_type, "actor_user_id": e.actor_user_id, "note": e.note, "created_at": e.created_at} for e in events]
