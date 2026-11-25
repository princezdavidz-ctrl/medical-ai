# Phase 3.18 — Facilities & Maintenance

## Scope
Hospital-scoped facility location hierarchy (campus, building, floor, wing, department, room and utility/external areas), controlled location status, maintenance requests linked to locations and optionally registered assets, independent approval, technician assignment, work start/completion and an append-only event history.

## Authorization
- `facilities_manager` and `hospital_admin`: create locations, approve/reject/cancel work orders, assign technicians and administer location status.
- `facilities_officer`, `maintenance_technician` and `biomedical_engineer`: view the facilities queue and create requests.
- Assigned `maintenance_technician` or `biomedical_engineer`: start and complete their own assigned work.
- All operations require active hospital membership and are tenant-scoped. A technician assignment must reference an active membership in the same hospital with an allowed facilities/maintenance role.

## API
- `POST /api/v1/facilities/locations`
- `GET /api/v1/facilities/locations`
- `PATCH /api/v1/facilities/locations/{location_id}/status`
- `POST /api/v1/facilities/work-orders`
- `GET /api/v1/facilities/work-orders?status_filter=requested`
- `POST /api/v1/facilities/work-orders/{order_id}/approve`
- `POST /api/v1/facilities/work-orders/{order_id}/reject`
- `POST /api/v1/facilities/work-orders/{order_id}/assign`
- `POST /api/v1/facilities/work-orders/{order_id}/start`
- `POST /api/v1/facilities/work-orders/{order_id}/complete`
- `POST /api/v1/facilities/work-orders/{order_id}/cancel`
- `GET /api/v1/facilities/work-orders/{order_id}/events`

## Workflow and controls
1. Facility location codes and work-order numbers are unique per hospital. A location's optional parent must be an active location in the same hospital.
2. A work order must reference an active location and, when supplied, an active equipment/asset record in the same hospital.
3. A manager other than the requester must approve or reject a requested work order. A work order cannot be approved by its requester.
4. Only active maintenance technicians/biomedical engineers (or designated facilities managers) may be assigned. Only the assigned technician may start and complete work; a facilities manager may complete an in-progress order.
5. Work orders move through requested → approved → assigned → in_progress → completed. Requested work can be rejected; requested/approved/assigned work can be cancelled. Completed, rejected and cancelled states are terminal.
6. Location deactivation/closure is blocked while active direct child locations or open maintenance work orders remain. Closed locations cannot be reactivated.
7. Work-order lifecycle events are append-only and database-protected against update/delete. Every lifecycle transition also emits an audit event.

## Boundaries
This milestone does not include preventive maintenance schedules, spare-parts consumption, maintenance costing, vendor dispatch/contracts, SLA/uptime analytics, utilities meter readings, fire-system monitoring, building access control, IoT/BMS integrations, clinical equipment calibration/certification, statutory inspection scheduling or asset depreciation. It does not automatically change equipment clinical availability or certify medical-device safety. Those require dedicated workflows and Phase 4 integrations.

## Phase 5 verification
Automated tests are intentionally deferred. Verify migrations, RLS, cross-tenant IDs, role separation, independent approval, concurrent state transitions, assignment membership, event immutability, location hierarchy and terminal-state rules in the central Phase 5 test campaign.
