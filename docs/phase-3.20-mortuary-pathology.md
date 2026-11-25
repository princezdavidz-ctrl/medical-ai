# Phase 3.20 — Mortuary & Pathology

## Scope
Hospital-scoped mortuary case intake and body identification, storage location tracking, custody movement ledger, legal holds, verified release authorizations, personal-effects inventory and controlled release. Pathology covers case registration, legal authority verification for autopsy/forensic cases, specimen accessioning and lifecycle, pathologist assignment, versioned reports and signed finalization.

## Authorization
- Mortuary: `mortuary_officer`, `mortuary_manager`, `hospital_admin`; managers/admin independently verify release authority, apply/lift legal holds and authorize body/property release.
- Pathology: `pathology_technician`, `pathologist`, `pathology_manager`, `hospital_admin`; managers/admin verify autopsy/forensic authority and assign pathologists. Assigned pathologists author/finalize reports; managers/admin may perform controlled overrides.
- Every record is hospital-scoped with RLS and composite patient/encounter/case foreign keys.

## API
### Mortuary
- `POST/GET /api/v1/mortuary-pathology/cases`
- `POST /api/v1/mortuary-pathology/cases/{case_id}/authorizations`
- `GET /api/v1/mortuary-pathology/cases/{case_id}/authorizations`
- `POST /api/v1/mortuary-pathology/authorizations/{authorization_id}/decision`
- `POST /api/v1/mortuary-pathology/authorizations/{authorization_id}/revoke`
- `POST /api/v1/mortuary-pathology/cases/{case_id}/movements`
- `POST /api/v1/mortuary-pathology/cases/{case_id}/legal-hold`
- `POST /api/v1/mortuary-pathology/cases/{case_id}/release`
- `POST/GET /api/v1/mortuary-pathology/cases/{case_id}/property`
- `PATCH /api/v1/mortuary-pathology/property/{property_id}/custody`
- `GET /api/v1/mortuary-pathology/cases/{case_id}/movements`

### Pathology
- `POST/GET /api/v1/mortuary-pathology/pathology/cases`
- `POST /api/v1/mortuary-pathology/pathology/cases/{case_id}/verify-authority`
- `POST /api/v1/mortuary-pathology/pathology/cases/{case_id}/assign`
- `POST/GET /api/v1/mortuary-pathology/pathology/cases/{case_id}/specimens`
- `PATCH /api/v1/mortuary-pathology/pathology/specimens/{specimen_id}/status`
- `POST/GET /api/v1/mortuary-pathology/pathology/cases/{case_id}/reports`
- `POST /api/v1/mortuary-pathology/pathology/reports/{report_id}/finalize`
- `POST /api/v1/mortuary-pathology/pathology/cases/{case_id}/close`
- `GET /api/v1/mortuary-pathology/pathology/cases/{case_id}/events`

## Mortuary custody and release rules
1. Every body receives a unique hospital case number and body reference; patient and optional encounter must belong to the same hospital and patient.
2. Body movements are append-only. The current storage location is updated alongside the movement ledger.
3. A legal hold blocks release. Applying a hold requires a recorded reason and authority reference, attributes the actor and timestamp, and places the case in retained-by-authority status; only a mortuary manager/admin can lift it.
4. Release requires a verified, non-revoked authorization with a protected vault evidence reference, explicit release-pending state, recipient identity details and resolution of every personal-effects item (released or retained).
5. Authorization verification is independent: the submitter cannot verify their own authority. Releasing a body does not certify cause of death or replace statutory death registration.

## Pathology authority and report rules
1. Autopsy and forensic cases require an authority type and reference. Forensic cases are limited to court order, coroner directive or public-health order.
2. A pathology manager/admin must independently verify authority and store a vault evidence reference before specimens can be added for autopsy/forensic cases.
3. Specimen accession numbers are unique per hospital; specimen transitions are collected → received → processing → processed → archived, with rejection available before completion. Receipt actor/time are recorded.
4. Reports require at least one processed/archived specimen, are versioned, and must be signed by the authoring pathologist or a pathology manager/admin.
5. Final reports are immutable at database level. Corrections require a new report version; the prior signed version remains retained.

## Boundaries
No cause-of-death determination, death certificate issuance, forensic chain-of-custody evidence vault, police/coroner/registrar integrations, body transport, cremation/burial scheduling, funeral-home portal, DNA identification, tissue banking, organ donation, histology image analysis, automated diagnosis, AI pathology interpretation, lab instrument integration or national pathology registry exchange is included. Statutory legal requirements and retention schedules must be configured and verified in the later compliance/integration phases; this module does not itself establish legal sufficiency.

## Phase 5 verification
All automated tests are deferred. Validate mortuary custody, authorization independence, legal holds, property reconciliation, release controls, pathology authority verification, specimen lifecycle, report versioning, final-report immutability, RLS and concurrency in the central Phase 5 test campaign.
