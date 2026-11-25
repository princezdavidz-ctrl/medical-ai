from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import HospitalMembership, Role
from app.models.inventory import (
    AssetRecord, GoodsReceipt, GoodsReceiptLine, InventoryItem,
    InventoryMovement, InventoryStockBalance, InventoryWarehouse,
)
from app.models.procurement import PurchaseOrder, PurchaseOrderLine
from app.schemas.inventory import (
    ItemCreate, ItemRead, WarehouseCreate, WarehouseRead,
    ReceiptCreate, ReceiptRead, AssetCreate, AssetStatusUpdate,
)

router = APIRouter(prefix="/inventory", tags=["inventory and asset management"])
_STAFF = {"inventory_officer", "storekeeper", "inventory_manager", "supply_chain_manager", "hospital_admin"}
_MANAGERS = {"inventory_manager", "supply_chain_manager", "hospital_admin"}
_ASSET_MANAGERS = {"asset_manager", "facilities_manager", "hospital_admin"}


def _role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    membership = db.scalar(select(HospitalMembership).join(Role, Role.id == HospitalMembership.role_id).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _require(db: Session, user_id: UUID, hospital_id: UUID, allowed: set[str]) -> str:
    role = _role(db, user_id, hospital_id)
    if not role or role not in allowed:
        raise HTTPException(status_code=403, detail={"code": "inventory_role_not_authorized"})
    return role


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource: str, item_id: UUID, metadata=None) -> None:
    write_audit_event(db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
                      resource_type=resource, resource_id=str(item_id), metadata=metadata or {})


@router.post("/items", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MANAGERS)
    item = InventoryItem(hospital_id=hospital_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(item)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "inventory.item.created", "inventory_item", item.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "inventory_item_code_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.get("/items", response_model=list[ItemRead])
def list_items(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _STAFF | _MANAGERS)
    return db.scalars(select(InventoryItem).where(InventoryItem.hospital_id == hospital_id).order_by(InventoryItem.name)).all()


@router.post("/warehouses", response_model=WarehouseRead, status_code=status.HTTP_201_CREATED)
def create_warehouse(payload: WarehouseCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MANAGERS)
    item = InventoryWarehouse(hospital_id=hospital_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(item)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "inventory.warehouse.created", "inventory_warehouse", item.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "warehouse_code_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.get("/warehouses", response_model=list[WarehouseRead])
def list_warehouses(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _STAFF | _MANAGERS)
    return db.scalars(select(InventoryWarehouse).where(InventoryWarehouse.hospital_id == hospital_id).order_by(InventoryWarehouse.name)).all()


@router.post("/goods-receipts", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
def create_receipt(payload: ReceiptCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _STAFF | _MANAGERS)
    order = db.scalar(select(PurchaseOrder).where(
        PurchaseOrder.id == payload.purchase_order_id, PurchaseOrder.hospital_id == hospital_id,
        PurchaseOrder.status.in_(["issued", "partially_received"]),
    ))
    warehouse = db.scalar(select(InventoryWarehouse).where(
        InventoryWarehouse.id == payload.warehouse_id, InventoryWarehouse.hospital_id == hospital_id,
        InventoryWarehouse.status == "active",
    ))
    if order is None:
        raise HTTPException(status_code=409, detail={"code": "issued_purchase_order_required"})
    if warehouse is None:
        raise HTTPException(status_code=404, detail={"code": "active_warehouse_not_found"})
    line_ids = [line.purchase_order_line_id for line in payload.lines]
    if len(set(line_ids)) != len(line_ids):
        raise HTTPException(status_code=422, detail={"code": "duplicate_purchase_order_line"})
    po_lines = db.scalars(select(PurchaseOrderLine).where(
        PurchaseOrderLine.hospital_id == hospital_id,
        PurchaseOrderLine.purchase_order_id == order.id,
        PurchaseOrderLine.id.in_(line_ids),
    )).all()
    po_by_id = {line.id: line for line in po_lines}
    if len(po_by_id) != len(line_ids):
        raise HTTPException(status_code=422, detail={"code": "purchase_order_line_mismatch"})
    item_ids = [line.inventory_item_id for line in payload.lines]
    items = db.scalars(select(InventoryItem).where(
        InventoryItem.hospital_id == hospital_id, InventoryItem.id.in_(item_ids),
        InventoryItem.status == "active",
    )).all()
    item_by_id = {item.id: item for item in items}
    if len(item_by_id) != len(set(item_ids)):
        raise HTTPException(status_code=422, detail={"code": "active_inventory_item_required"})
    for line in payload.lines:
        item = item_by_id[line.inventory_item_id]
        if item.tracking_mode == "serial" and (line.serial_number is None or line.quantity_received != Decimal("1")):
            raise HTTPException(status_code=422, detail={"code": "serial_item_requires_one_unit_and_serial"})
        if item.tracking_mode != "serial" and line.serial_number is not None:
            raise HTTPException(status_code=422, detail={"code": "serial_number_not_allowed_for_tracking_mode"})
        if item.tracking_mode == "lot" and not line.batch_number:
            raise HTTPException(status_code=422, detail={"code": "lot_item_requires_batch_number"})
        if item.tracking_mode != "lot" and line.batch_number is not None:
            raise HTTPException(status_code=422, detail={"code": "batch_number_not_allowed_for_tracking_mode"})
        if line.expiry_at is not None and line.expiry_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail={"code": "expired_stock_not_accepted"})
    receipt = GoodsReceipt(
        hospital_id=hospital_id, purchase_order_id=order.id, warehouse_id=warehouse.id,
        receipt_number=payload.receipt_number, delivery_note_reference=payload.delivery_note_reference,
        received_by_user_id=user.id, status="draft",
    )
    db.add(receipt)
    try:
        db.flush()
        for line in payload.lines:
            db.add(GoodsReceiptLine(
                hospital_id=hospital_id, goods_receipt_id=receipt.id, purchase_order_id=order.id,
                **line.model_dump(),
            ))
        _audit(db, hospital_id, user.id, "inventory.goods_receipt.created", "goods_receipt", receipt.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "goods_receipt_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(receipt)
    return receipt


@router.post("/goods-receipts/{receipt_id}/post", response_model=ReceiptRead)
def post_receipt(receipt_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MANAGERS)
    receipt = db.scalar(select(GoodsReceipt).where(
        GoodsReceipt.id == receipt_id, GoodsReceipt.hospital_id == hospital_id,
    ).with_for_update())
    if receipt is None or receipt.status != "draft":
        raise HTTPException(status_code=404, detail={"code": "draft_goods_receipt_not_found"})
    order = db.scalar(select(PurchaseOrder).where(
        PurchaseOrder.id == receipt.purchase_order_id, PurchaseOrder.hospital_id == hospital_id,
    ).with_for_update())
    if order is None or order.status not in ("issued", "partially_received"):
        raise HTTPException(status_code=409, detail={"code": "purchase_order_not_receivable"})
    lines = db.scalars(select(GoodsReceiptLine).where(
        GoodsReceiptLine.hospital_id == hospital_id, GoodsReceiptLine.goods_receipt_id == receipt.id,
    ).order_by(GoodsReceiptLine.purchase_order_line_id).with_for_update()).all()
    if not lines:
        raise HTTPException(status_code=409, detail={"code": "goods_receipt_requires_lines"})
    for line in lines:
        po_line = db.scalar(select(PurchaseOrderLine).where(
            PurchaseOrderLine.hospital_id == hospital_id,
            PurchaseOrderLine.purchase_order_id == order.id,
            PurchaseOrderLine.id == line.purchase_order_line_id,
        ).with_for_update())
        if po_line is None:
            raise HTTPException(status_code=409, detail={"code": "purchase_order_line_mismatch"})
        already_received = db.scalar(select(func.coalesce(func.sum(GoodsReceiptLine.quantity_received), 0)).join(
            GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id,
        ).where(
            GoodsReceiptLine.hospital_id == hospital_id,
            GoodsReceiptLine.purchase_order_line_id == po_line.id,
            GoodsReceipt.status == "posted",
        ))
        if Decimal(str(already_received or 0)) + line.quantity_received > po_line.quantity:
            raise HTTPException(status_code=409, detail={"code": "receipt_exceeds_ordered_quantity"})
        item = db.scalar(select(InventoryItem).where(
            InventoryItem.id == line.inventory_item_id, InventoryItem.hospital_id == hospital_id,
            InventoryItem.status == "active",
        ))
        if item is None:
            raise HTTPException(status_code=409, detail={"code": "inventory_item_inactive"})
        balance = db.scalar(select(InventoryStockBalance).where(
            InventoryStockBalance.hospital_id == hospital_id,
            InventoryStockBalance.warehouse_id == receipt.warehouse_id,
            InventoryStockBalance.inventory_item_id == item.id,
        ).with_for_update())
        if balance is None:
            balance = InventoryStockBalance(
                hospital_id=hospital_id, warehouse_id=receipt.warehouse_id,
                inventory_item_id=item.id, quantity_on_hand=Decimal("0"), quantity_reserved=Decimal("0"),
            )
            db.add(balance)
            db.flush()
        balance.quantity_on_hand += line.quantity_received
        db.add(InventoryMovement(
            hospital_id=hospital_id, warehouse_id=receipt.warehouse_id, inventory_item_id=item.id,
            movement_type="receipt", quantity=line.quantity_received, reference_type="goods_receipt",
            reference_id=receipt.id, actor_user_id=user.id, note="Posted purchase-order goods receipt",
        ))
    receipt.status, receipt.posted_by_user_id, receipt.posted_at = "posted", user.id, datetime.now(timezone.utc)
    db.flush()
    all_po_lines = db.scalars(select(PurchaseOrderLine).where(
        PurchaseOrderLine.hospital_id == hospital_id, PurchaseOrderLine.purchase_order_id == order.id,
    )).all()
    fully_received = True
    for po_line in all_po_lines:
        received = db.scalar(select(func.coalesce(func.sum(GoodsReceiptLine.quantity_received), 0)).join(
            GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.goods_receipt_id,
        ).where(
            GoodsReceiptLine.hospital_id == hospital_id,
            GoodsReceiptLine.purchase_order_line_id == po_line.id,
            GoodsReceipt.status == "posted",
        ))
        if Decimal(str(received or 0)) < po_line.quantity:
            fully_received = False
            break
    order.status = "received" if fully_received else "partially_received"
    _audit(db, hospital_id, user.id, "inventory.goods_receipt.posted", "goods_receipt", receipt.id, {"line_count": len(lines)})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(receipt)
    return receipt


@router.get("/stock-balances")
def list_stock_balances(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _STAFF | _MANAGERS)
    rows = db.execute(select(
        InventoryStockBalance.id, InventoryStockBalance.warehouse_id,
        InventoryStockBalance.inventory_item_id, InventoryStockBalance.quantity_on_hand,
        InventoryStockBalance.quantity_reserved, InventoryStockBalance.updated_at,
    ).where(InventoryStockBalance.hospital_id == hospital_id).order_by(
        InventoryStockBalance.updated_at.desc(),
    )).all()
    return [dict(row._mapping) for row in rows]


@router.get("/movements")
def list_movements(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _STAFF | _MANAGERS)
    rows = db.scalars(select(InventoryMovement).where(
        InventoryMovement.hospital_id == hospital_id,
    ).order_by(InventoryMovement.created_at.desc()).limit(500)).all()
    return [{
        "id": row.id, "warehouse_id": row.warehouse_id, "inventory_item_id": row.inventory_item_id,
        "movement_type": row.movement_type, "quantity": row.quantity, "reference_type": row.reference_type,
        "reference_id": row.reference_id, "actor_user_id": row.actor_user_id, "created_at": row.created_at,
    } for row in rows]


@router.post("/assets", status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _ASSET_MANAGERS | _MANAGERS)
    item = db.scalar(select(InventoryItem).where(
        InventoryItem.id == payload.inventory_item_id, InventoryItem.hospital_id == hospital_id,
        InventoryItem.status == "active", InventoryItem.item_type.in_(["asset", "equipment"]),
    ))
    warehouse = db.scalar(select(InventoryWarehouse).where(
        InventoryWarehouse.id == payload.warehouse_id, InventoryWarehouse.hospital_id == hospital_id,
        InventoryWarehouse.status == "active",
    ))
    if item is None or warehouse is None:
        raise HTTPException(status_code=404, detail={"code": "active_asset_item_and_warehouse_required"})
    if payload.warranty_until and payload.acquired_at and payload.warranty_until < payload.acquired_at:
        raise HTTPException(status_code=422, detail={"code": "warranty_before_acquisition"})
    asset = AssetRecord(hospital_id=hospital_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(asset)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "inventory.asset.created", "asset_record", asset.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "asset_tag_or_serial_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(asset)
    return asset


@router.get("/assets")
def list_assets(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _STAFF | _MANAGERS | _ASSET_MANAGERS)
    rows = db.scalars(select(AssetRecord).where(
        AssetRecord.hospital_id == hospital_id,
    ).order_by(AssetRecord.asset_tag)).all()
    return [{
        "id": row.id, "inventory_item_id": row.inventory_item_id, "warehouse_id": row.warehouse_id,
        "asset_tag": row.asset_tag, "serial_number": row.serial_number, "manufacturer": row.manufacturer,
        "model_number": row.model_number, "acquired_at": row.acquired_at, "warranty_until": row.warranty_until,
        "status": row.status, "created_at": row.created_at,
    } for row in rows]


@router.patch("/assets/{asset_id}/status")
def update_asset_status(asset_id: UUID, payload: AssetStatusUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _ASSET_MANAGERS)
    asset = db.scalar(select(AssetRecord).where(
        AssetRecord.id == asset_id, AssetRecord.hospital_id == hospital_id,
    ).with_for_update())
    if asset is None:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found"})
    if asset.status in ("retired", "disposed"):
        raise HTTPException(status_code=409, detail={"code": "asset_terminal_status"})
    asset.status = payload.status
    _audit(db, hospital_id, user.id, "inventory.asset.status_changed", "asset_record", asset.id, {"status": payload.status})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(asset)
    return asset
