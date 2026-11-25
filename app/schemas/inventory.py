from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    category: str = Field(min_length=2, max_length=100)
    item_type: str = Field(pattern="^(consumable|equipment|asset)$")
    tracking_mode: str = Field(default="quantity", pattern="^(quantity|lot|serial)$")
    unit_of_measure: str = Field(min_length=1, max_length=40)
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)

class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    item_code: str
    name: str
    category: str
    item_type: str
    tracking_mode: str
    unit_of_measure: str
    reorder_level: Decimal
    status: str
    created_at: datetime

class WarehouseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warehouse_code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    location_description: str | None = Field(default=None, max_length=240)

class WarehouseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    warehouse_code: str
    name: str
    location_description: str | None
    status: str
    created_at: datetime

class ReceiptLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchase_order_line_id: UUID
    inventory_item_id: UUID
    quantity_received: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    batch_number: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=160)
    expiry_at: datetime | None = None
    unit_cost: Decimal = Field(ge=0, max_digits=16, decimal_places=2)

class ReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchase_order_id: UUID
    warehouse_id: UUID
    receipt_number: str = Field(min_length=2, max_length=80)
    delivery_note_reference: str | None = Field(default=None, max_length=160)
    lines: list[ReceiptLineCreate] = Field(min_length=1, max_length=200)

class ReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    purchase_order_id: UUID
    warehouse_id: UUID
    receipt_number: str
    status: str
    received_by_user_id: UUID
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    created_at: datetime

class AssetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inventory_item_id: UUID
    warehouse_id: UUID
    asset_tag: str = Field(min_length=2, max_length=100)
    serial_number: str | None = Field(default=None, max_length=160)
    manufacturer: str | None = Field(default=None, max_length=160)
    model_number: str | None = Field(default=None, max_length=120)
    acquired_at: datetime | None = None
    warranty_until: datetime | None = None

class AssetStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(in_service|under_maintenance|retired|disposed)$")
