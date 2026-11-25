# Phase 3.17 — Inventory & Asset Management

## Scope
Hospital-scoped item catalog, warehouse directory, goods receipt against an issued purchase order, quantity/lot/serial tracking metadata, stock-on-hand projections, append-only inventory movements, and individually tagged equipment/fixed-asset records.

## Authorization
- `inventory_manager`, `supply_chain_manager`, and `hospital_admin`: manage catalog and warehouses, post receipts, and administer stock operations.
- `inventory_officer` and `storekeeper`: view catalog/warehouses, create draft receipts, and view balances and movement history.
- `asset_manager`, `facilities_manager`, and `hospital_admin`: create and manage asset lifecycle status.
- All operations are scoped to the active hospital membership and RLS context. Cross-hospital identifiers are rejected.

## API
- `POST/GET /api/v1/inventory/items`
- `POST/GET /api/v1/inventory/warehouses`
- `POST /api/v1/inventory/goods-receipts`
- `POST /api/v1/inventory/goods-receipts/{receipt_id}/post`
- `GET /api/v1/inventory/stock-balances`
- `GET /api/v1/inventory/movements`
- `POST/GET /api/v1/inventory/assets`
- `PATCH /api/v1/inventory/assets/{asset_id}/status`

## Receipt and stock rules
1. A receipt can reference only an issued or partially received purchase order from the same hospital and an active warehouse.
2. Every received line must reference a purchase-order line belonging to that exact purchase order and an active inventory item in the same hospital.
3. Serial-tracked items require exactly one unit and a serial number; lot-tracked items require a batch number; incompatible tracking metadata is rejected.
4. Posting locks the receipt, purchase order and purchase-order lines, checks cumulative posted receipts against ordered quantities, and atomically updates stock balances, immutable movement events, receipt state and purchase-order receipt state.
5. Draft receipts do not affect stock. Reposting is denied. Inventory movement rows are append-only at database level.
6. Asset records are individual tagged equipment/assets, distinct from consumable stock. Asset tags and supplied serials are unique within a hospital.

## Boundaries
No stock issue/reservation, inter-warehouse transfer, cycle count, write-off/adjustment workflow, valuation/FIFO/weighted-average costing, depreciation, maintenance work orders, supplier portal, barcode hardware, RFID, device telemetry, or external ERP integration is included. Those require separate workflows or later modules/integrations. Receipt unit cost is retained as procurement evidence and is not a financial valuation engine. No clinical device safety certification is inferred.

## Phase 5 verification
All automated tests are deferred to the central Phase 5 campaign. Do not treat this module as production-verified until migration, authorization, concurrency, RLS, and API contract tests have passed with recorded evidence.
