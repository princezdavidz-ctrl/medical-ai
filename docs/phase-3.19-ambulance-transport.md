# Phase 3.19 — Ambulance & Interfacility Transport

## Scope
Consent-gated interfacility transfer coordination: origin-hospital transfer request, receiving-hospital acceptance with a recorded bed reference, ambulance fleet inventory, driver/crew assignment, dispatch, manually recorded location updates, receiving-hospital arrival confirmation, origin-fleet vehicle release and an append-only event timeline.

## Authorization
- Origin roles: `transfer_coordinator`, `ambulance_dispatcher`, `emergency_physician`, `emergency_nurse`, `hospital_admin`.
- Fleet managers: `ambulance_manager`, `fleet_manager`, `hospital_admin`.
- Receiving roles: `bed_manager`, `admissions_officer`, `receiving_clinician`, `emergency_physician`, `hospital_admin`.
- Driver/crew assignments require active same-origin-hospital membership with `ambulance_driver`, `paramedic`, `emergency_nurse` or `ambulance_officer`.
- The origin transfer record remains origin-hospital-only. The receiving hospital sees a separate minimized offer containing transfer reference, priority and pickup/drop-off descriptions, not patient/encounter identifiers, clinical reason or consent record. The event timeline is shared for operational tracking.

## Consent gate
Creating a transfer requires the exact supplied patient consent record to be active, granted, not withdrawn or expired, and to match purpose `inter_hospital_transfer`. Its scope must include data categories `identity` and `clinical_summary`, and permitted use `transfer_of_care`. The transfer record is tenant-bound to that exact patient consent and encounter. A consent check is repeated at request creation; later consent withdrawal handling is a Phase 5 verification and operational release control.

## API
- `POST/GET /api/v1/transport/vehicles`
- `PATCH /api/v1/transport/vehicles/{vehicle_id}/status`
- `POST/GET /api/v1/transport/requests` (origin hospital)
- `GET /api/v1/transport/receiving/requests` (receiving hospital, minimized offers)
- `POST /api/v1/transport/requests/{request_id}/receiving-acceptance`
- `POST /api/v1/transport/requests/{request_id}/receiving-rejection`
- `POST /api/v1/transport/requests/{request_id}/assign-vehicle`
- `POST /api/v1/transport/requests/{request_id}/dispatch`
- `POST /api/v1/transport/requests/{request_id}/tracking`
- `POST /api/v1/transport/requests/{request_id}/arrival-confirmation` (receiving hospital)
- `POST /api/v1/transport/requests/{request_id}/release-vehicle` (origin fleet)
- `POST /api/v1/transport/requests/{request_id}/cancel`
- `GET /api/v1/transport/requests/{request_id}/events` (participants)

## Workflow
1. Origin staff creates a transfer only for an active patient and active encounter, with an exact active transfer-of-care authorization.
2. The system creates a minimized receiving offer in the destination hospital's security scope. The destination's authorized staff records bed acceptance with a bed reference, or rejects the offer with a reason.
3. Origin fleet staff assigns an available origin-hospital ambulance, driver and optional crew; then dispatches it.
4. Assigned driver/crew record manual GPS coordinates and/or operational notes while en route. Latitude/longitude must be supplied together and validated to geographic bounds.
5. Receiving staff confirms arrival. Origin fleet staff then reconciles the receiving arrival and releases the vehicle back to the available fleet.
6. Transfer and event records are hospital-isolated. Event rows are append-only at database level.

## Boundaries
This milestone is interfacility transfer coordination only. Bed acceptance is a receiving-staff attestation with a bed reference; it does not reserve or occupy an inpatient bed in Module 4. GPS updates are manually submitted; live GPS, routing/ETA, dispatch radio, ambulance telematics, emergency-service integrations, external fleet operators, billing, clinical handover document exchange and automatic patient-record sharing are not included. Patient records are not exposed to the receiving hospital by this module; any clinical record exchange must use the separately governed consent-based record-sharing workflow and Phase 4 integrations. No clinical triage, treatment or transport fitness decision is automated.
