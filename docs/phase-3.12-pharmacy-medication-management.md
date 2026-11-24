# Phase 3.12 — Pharmacy & Medication Management

## Scope implemented

Pharmacy provides a governed hospital medication catalog, encounter-linked prescriptions, independent pharmacist review, review history and partial/full dispensing records.

### Workflow

1. **Medication catalog drafting** — pharmacy managers/pharmacists create hospital-specific definitions with generic/brand name, active ingredient, strength, dosage form and optional default route. Definitions remain drafts and cannot be prescribed.
2. **Independent catalog approval** — a different registered pharmacist approves the draft. A nonblank professional-registration value must be present on the hospital membership; the platform does not independently verify that credential.
3. **Clinician prescription** — an authorized clinician with an active care assignment creates an order against an in-progress encounter. The patient is derived from the encounter; clients cannot submit an unrelated patient ID.
4. **Pharmacy queue** — pharmacy staff see orders routed to their own pharmacy department, with minimum-necessary patient identity and current order state.
5. **Pharmacist review** — a registered pharmacist other than the prescriber approves, places on hold or rejects the order with a recorded note. Held orders can be reviewed again; rejected orders are terminal.
6. **Dispensing** — a registered pharmacist records one or more dispense events. Quantity units must match the prescription and cumulative dispensed quantity cannot exceed the prescribed quantity. The order becomes partially dispensed or dispensed when the prescribed quantity is reached.
7. **Cancellation** — the prescribing clinician or pharmacy supervisor can cancel an eligible order before any quantity is dispensed. Every cancellation requires a reason.
8. **History** — pharmacist review events and dispense events are append-only at the database level.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/pharmacy/medication-definitions` | Create a draft medication definition |
| POST | `/api/v1/pharmacy/medication-definitions/{definition_id}/approve` | Independently approve a medication definition |
| POST | `/api/v1/pharmacy/medication-definitions/{definition_id}/retire` | Retire an active definition with reason |
| GET | `/api/v1/pharmacy/medication-definitions` | List active medication definitions in permitted scope |
| POST | `/api/v1/pharmacy/encounters/{encounter_id}/orders` | Create a clinician prescription |
| GET | `/api/v1/pharmacy/orders` | View the pharmacy work queue |
| GET | `/api/v1/pharmacy/orders/{order_id}` | Read prescription, review events and dispense history |
| POST | `/api/v1/pharmacy/orders/{order_id}/review` | Approve, hold or reject a prescription |
| POST | `/api/v1/pharmacy/orders/{order_id}/dispenses` | Record a full or partial dispense |
| POST | `/api/v1/pharmacy/orders/{order_id}/cancel` | Cancel an eligible order with reason |

## Authorization, tenant isolation and audit

- Medication catalog actions are restricted to pharmacy catalog roles and the relevant pharmacy department.
- Catalog approval requires a different user from the creator.
- Prescription creation requires an active clinician role, in-progress encounter, active patient and active assignment to the exact patient/encounter/ordering department.
- Pharmacist review and dispensing require a nonblank professional-registration value and a pharmacy department membership. The platform does not independently verify professional credentials.
- A prescriber cannot review their own prescription.
- Pharmacy queue access is limited to the pharmacy department assigned on the order. Ordering clinicians can read only orders within their department and active patient-care assignment.
- Composite foreign keys bind orders to the same hospital, patient, encounter, ordering department, pharmacy department and medication definition.
- All medication tables enforce hospital row-level security.
- Review and dispense events are protected by database triggers against update/delete.
- Audit metadata records actor, action, resource ID and non-clinical state values; dose text, frequency, instructions and indication are not copied into audit metadata.
- Queue/order responses expose only MRN and given/family name for patient identification.

## Clinical safety boundaries

- No medication definitions, dosing regimens or clinical drug data are seeded.
- Dose and frequency are prescriber-entered text. When a catalog default route is present, the prescribed route must match it. The system does not calculate, recommend or adjust a dose, route, frequency, duration or quantity. Retiring a catalog item blocks new orders, review and further dispensing; any already partially dispensed order with remaining quantity requires manual clinical resolution and is not automatically substituted.
- No automated allergy, interaction, contraindication, pregnancy, renal/hepatic, age-based or duplicate-therapy checking is enabled in this module.
- No automatic substitution or generic-equivalence decision is made.
- Pharmacist review is an explicit human workflow; approval does not certify that an order is clinically appropriate.
- Dispensing records do not reserve or deduct stock. Inventory reconciliation, batch/expiry validation, controlled-drug registers and cold-chain controls remain separate integrations.
- This module does not administer medication or replace a nursing medication-administration record (MAR).
- No automated refill, patient notification, diagnosis, treatment advice or AI action is enabled.
- Final dispense events and review events cannot be edited or deleted through the application or database trigger path.
- No live patient data is seeded.

## Deferred integrations

- Inventory/stock reservation, batch and expiry validation, purchase/procurement and supplier management.
- Medication administration record (MAR), barcode bedside verification and nursing workflow integration.
- Drug catalog standards, RxNorm/ATC mappings, controlled-medicine rules and jurisdiction-specific prescribing requirements.
- Approved medication safety knowledge, interaction/contraindication checks and clinical decision support through the central AI platform after separate evaluation/release approval.
- Electronic prescription exchange, external pharmacy networks, insurance formularies, claims and patient refill workflows.
- Medication reconciliation, allergy reconciliation and discharge medication lists.

All medication catalog, prescription assignment, review, two-person separation, quantity arithmetic, partial dispensing, cancellation, tenant isolation, append-only history and audit checks are listed in the Phase 5 Test Register. Tests have not been executed for this milestone.
