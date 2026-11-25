from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import Department, HospitalMembership, Role
from app.models.procurement import (
    ProcurementVendor, PurchaseRequisition, PurchaseRequisitionLine,
    PurchaseOrder, PurchaseOrderLine, ProcurementEvent,
)
from app.schemas.procurement import (
    VendorCreate, VendorRead, RequisitionCreate, RequisitionRead,
    RequisitionDecision, PurchaseOrderCreate, PurchaseOrderRead, PurchaseOrderIssue,
)

router = APIRouter(prefix="/procurement", tags=["procurement and supply chain"])

_PROCUREMENT_STAFF = {"procurement_officer", "procurement_manager", "supply_chain_manager", "hospital_admin"}
_PROCUREMENT_APPROVERS = {"procurement_manager", "supply_chain_manager", "hospital_admin"}
_VENDOR_APPROVERS = {"procurement_manager", "supply_chain_manager", "hospital_admin"}


def _role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    membership = db.scalar(
        select(HospitalMembership).join(Role, Role.id == HospitalMembership.role_id).where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == user_id,
            HospitalMembership.status == "active",
        )
    )
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _require(db: Session, user_id: UUID, hospital_id: UUID, allowed: set[str]) -> str:
    role = _role(db, user_id, hospital_id)
    if not role:
        raise HTTPException(status_code=403, detail={"code": "procurement_membership_required"})
    if role not in allowed:
        raise HTTPException(status_code=403, detail={"code": "procurement_role_not_authorized"})
    return role


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource: str, item_id: UUID, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id,
        action=action, resource_type=resource, resource_id=str(item_id),
        metadata=metadata or {},
    )


def _event(db: Session, hospital_id: UUID, user_id: UUID, resource_type: str, resource_id: UUID, event_type: str, note=None):
    db.add(ProcurementEvent(
        hospital_id=hospital_id, actor_user_id=user_id,
        resource_type=resource_type, resource_id=resource_id,
        event_type=event_type, note=note,
    ))


@router.post("/vendors", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
def create_vendor(payload: VendorCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PROCUREMENT_STAFF)
    item = ProcurementVendor(
        hospital_id=hospital_id, created_by_user_id=user.id,
        status="draft", **payload.model_dump(),
    )
    db.add(item)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "procurement.vendor.created", "procurement_vendor", item.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "vendor_code_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.post("/vendors/{vendor_id}/approve", response_model=VendorRead)
def approve_vendor(vendor_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _VENDOR_APPROVERS)
    item = db.scalar(select(ProcurementVendor).where(
        ProcurementVendor.id == vendor_id,
        ProcurementVendor.hospital_id == hospital_id,
    ).with_for_update())
    if item is None or item.status != "draft":
        raise HTTPException(status_code=404, detail={"code": "draft_vendor_not_found"})
    if item.created_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_vendor_approval_required"})
    item.status, item.approved_by_user_id, item.approved_at = "active", user.id, datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "procurement.vendor.approved", "procurement_vendor", item.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.post("/requisitions", response_model=RequisitionRead, status_code=status.HTTP_201_CREATED)
def create_requisition(payload: RequisitionCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user.id,
        HospitalMembership.status == "active",
    ))
    if membership is None or membership.department_id != payload.department_id:
        raise HTTPException(status_code=403, detail={"code": "requisition_department_membership_required"})
    department = db.scalar(select(Department).where(
        Department.id == payload.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "active_department_not_found"})
    if payload.required_by is not None and payload.required_by < datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail={"code": "required_by_must_be_future"})
    item = PurchaseRequisition(
        hospital_id=hospital_id, department_id=payload.department_id,
        requisition_number=payload.requisition_number,
        purpose=payload.purpose, required_by=payload.required_by,
        requested_by_user_id=user.id, status="draft",
    )
    db.add(item)
    try:
        db.flush()
        for line in payload.lines:
            db.add(PurchaseRequisitionLine(
                hospital_id=hospital_id, requisition_id=item.id, **line.model_dump(),
            ))
        _audit(db, hospital_id, user.id, "procurement.requisition.created", "purchase_requisition", item.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "requisition_number_conflict"})
    _restore_context(db, user.id, hospital_id)
    return db.scalar(select(PurchaseRequisition).options(selectinload(PurchaseRequisition.lines)).where(
        PurchaseRequisition.id == item.id, PurchaseRequisition.hospital_id == hospital_id,
    ))


@router.post("/requisitions/{requisition_id}/submit", response_model=RequisitionRead)
def submit_requisition(requisition_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    item = db.scalar(select(PurchaseRequisition).where(
        PurchaseRequisition.id == requisition_id,
        PurchaseRequisition.hospital_id == hospital_id,
    ).with_for_update())
    if item is None or item.requested_by_user_id != user.id or item.status != "draft":
        raise HTTPException(status_code=404, detail={"code": "owned_draft_requisition_not_found"})
    count = db.scalar(select(PurchaseRequisitionLine.id).where(
        PurchaseRequisitionLine.hospital_id == hospital_id,
        PurchaseRequisitionLine.requisition_id == item.id,
    ).limit(1))
    if count is None:
        raise HTTPException(status_code=409, detail={"code": "requisition_requires_lines"})
    item.status, item.submitted_at = "submitted", datetime.now(timezone.utc)
    _event(db, hospital_id, user.id, "requisition", item.id, "submitted")
    _audit(db, hospital_id, user.id, "procurement.requisition.submitted", "purchase_requisition", item.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return db.scalar(select(PurchaseRequisition).options(selectinload(PurchaseRequisition.lines)).where(
        PurchaseRequisition.id == item.id, PurchaseRequisition.hospital_id == hospital_id,
    ))


@router.post("/requisitions/{requisition_id}/decision", response_model=RequisitionRead)
def decide_requisition(requisition_id: UUID, payload: RequisitionDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PROCUREMENT_APPROVERS)
    item = db.scalar(select(PurchaseRequisition).where(
        PurchaseRequisition.id == requisition_id,
        PurchaseRequisition.hospital_id == hospital_id,
    ).with_for_update())
    if item is None or item.status != "submitted":
        raise HTTPException(status_code=404, detail={"code": "submitted_requisition_not_found"})
    if item.requested_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_requisition_approval_required"})
    item.status = payload.outcome
    item.approved_by_user_id, item.approved_at = user.id, datetime.now(timezone.utc)
    item.decision_note = payload.note
    _event(db, hospital_id, user.id, "requisition", item.id, payload.outcome, payload.note)
    _audit(db, hospital_id, user.id, "procurement.requisition.decided", "purchase_requisition", item.id, {"outcome": payload.outcome})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return db.scalar(select(PurchaseRequisition).options(selectinload(PurchaseRequisition.lines)).where(
        PurchaseRequisition.id == item.id, PurchaseRequisition.hospital_id == hospital_id,
    ))


@router.post("/requisitions/{requisition_id}/purchase-orders", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
def create_purchase_order(requisition_id: UUID, payload: PurchaseOrderCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PROCUREMENT_STAFF)
    requisition = db.scalar(select(PurchaseRequisition).where(
        PurchaseRequisition.id == requisition_id,
        PurchaseRequisition.hospital_id == hospital_id,
    ).with_for_update())
    if requisition is None or requisition.status != "approved":
        raise HTTPException(status_code=409, detail={"code": "approved_requisition_required"})
    vendor = db.scalar(select(ProcurementVendor).where(
        ProcurementVendor.id == payload.vendor_id,
        ProcurementVendor.hospital_id == hospital_id,
        ProcurementVendor.status == "active",
    ))
    if vendor is None:
        raise HTTPException(status_code=404, detail={"code": "active_vendor_not_found"})
    lines = db.scalars(select(PurchaseRequisitionLine).where(
        PurchaseRequisitionLine.hospital_id == hospital_id,
        PurchaseRequisitionLine.requisition_id == requisition.id,
    )).all()
    line_ids = {line.id for line in lines}
    if set(payload.unit_prices.keys()) != line_ids:
        raise HTTPException(status_code=422, detail={"code": "unit_prices_must_match_all_requisition_lines"})
    if any(line.currency != payload.currency for line in lines):
        raise HTTPException(status_code=422, detail={"code": "purchase_order_currency_mismatch"})
    total = Decimal("0")
    for line in lines:
        total += (line.quantity * payload.unit_prices[line.id]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    order = PurchaseOrder(
        hospital_id=hospital_id, vendor_id=vendor.id, requisition_id=requisition.id,
        order_number=payload.order_number, currency=payload.currency,
        total_amount=total, created_by_user_id=user.id, status="draft",
    )
    db.add(order)
    try:
        db.flush()
        for line in lines:
            price = payload.unit_prices[line.id]
            line_total = (line.quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            db.add(PurchaseOrderLine(
                hospital_id=hospital_id, purchase_order_id=order.id,
                requisition_line_id=line.id, item_description=line.item_description,
                quantity=line.quantity, unit_of_measure=line.unit_of_measure,
                unit_price=price, line_total=line_total,
            ))
        requisition.status = "converted"
        _event(db, hospital_id, user.id, "purchase_order", order.id, "created")
        _audit(db, hospital_id, user.id, "procurement.purchase_order.created", "purchase_order", order.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "purchase_order_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(order)
    return order


@router.post("/purchase-orders/{order_id}/issue", response_model=PurchaseOrderRead)
def issue_purchase_order(order_id: UUID, payload: PurchaseOrderIssue, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PROCUREMENT_APPROVERS)
    order = db.scalar(select(PurchaseOrder).where(
        PurchaseOrder.id == order_id,
        PurchaseOrder.hospital_id == hospital_id,
    ).with_for_update())
    if order is None or order.status != "draft":
        raise HTTPException(status_code=404, detail={"code": "draft_purchase_order_not_found"})
    if order.created_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_purchase_order_issue_required"})
    order.status, order.issued_by_user_id, order.issued_at = "issued", user.id, datetime.now(timezone.utc)
    _event(db, hospital_id, user.id, "purchase_order", order.id, "issued", payload.note)
    _audit(db, hospital_id, user.id, "procurement.purchase_order.issued", "purchase_order", order.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(order)
    return order
