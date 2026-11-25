# Phase 3.16 — Procurement & Supply Chain

## Scope delivered

This module provides hospital-scoped vendor registration, departmental purchase requisitions, approval and purchase-order issuance. It is a purchasing workflow foundation; inventory receipts and stock balances belong to Module 17.

### Vendor directory
- Hospital-scoped vendor code, legal name, vendor type and limited contact/registration references.
- New vendors start as draft and require independent procurement-manager approval before use.
- Draft/active vendor state is explicit; only active vendors can be selected for a purchase order.

### Purchase requisitions
- A hospital member may request goods/services only for their own active department.
- Requisitions contain one or more item lines, quantities, units of measure, optional specifications and estimated costs.
- Submitter cannot approve their own requisition; approval/rejection records reviewer and timestamp.
- Submitted requisitions are immutable through this API; a single approved requisition can be converted to one purchase order.

### Purchase orders
- Purchase orders can only be created from an approved requisition and an active vendor in the same hospital.
- Unit prices must be supplied for every requisition line; currency must match all requisition lines.
- Order totals are calculated server-side from quantities and unit prices.
- A separate authorized user must issue the order; order state and issue attribution are persisted.
- Procurement events are append-only.

## API surface

- POST /api/v1/procurement/vendors
- POST /api/v1/procurement/vendors/{vendor_id}/approve
- POST /api/v1/procurement/requisitions
- POST /api/v1/procurement/requisitions/{requisition_id}/submit
- POST /api/v1/procurement/requisitions/{requisition_id}/decision
- POST /api/v1/procurement/requisitions/{requisition_id}/purchase-orders
- POST /api/v1/procurement/purchase-orders/{order_id}/issue

## Authorization and tenant boundaries

- Procurement roles: procurement_officer, procurement_manager, supply_chain_manager and hospital_admin.
- Department requisitions require active membership in the selected department.
- Vendor approval, requisition decisions and purchase-order issuance require procurement manager/supply-chain manager/hospital admin privileges and separation of duties.
- PostgreSQL RLS is enabled for all procurement tables. Composite hospital foreign keys protect department, vendor, requisition and line relationships.

## Explicit exclusions

- Goods receipt, warehouse/bin management, stock-on-hand, lot/batch/serial tracking and inventory valuation (Module 17).
- Supplier portals, tender/e-procurement platforms, bid evaluation, contract lifecycle and electronic signatures.
- Budget availability, commitment accounting, tax/VAT computation and accounts-payable settlement.
- Live supplier registry, KRA PIN, eTIMS, banking or payment integrations.
- Automatic purchase orders, live patient data or clinical decisions.

Validation is deferred to Phase 5; no backend tests were run for this milestone.
