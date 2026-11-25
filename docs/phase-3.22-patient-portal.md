# Phase 3.22 — Patient Portal

## Scope
A hospital-scoped, read-only patient self-service API. Existing user accounts are linked to patient records only after independent staff verification. Verified self and legally documented proxy links receive explicit access scopes and optional expiry. The portal exposes patient demographics, encounter history, final laboratory results, medication orders, issued invoices and consent records.

## Account and identity controls
- The portal does not create user accounts. It authenticates existing accounts through a dedicated patient-token exchange.
- A patient record is never matched using MRN, date of birth or name alone.
- Staff create a pending link and a different authorized staff member verifies it. The requester cannot verify their own request.
- Self links require an approved identity-verification method and protected evidence reference. New links default to `profile` and `encounters`; staff must explicitly grant laboratory, medication, invoice or consent scopes.
- Parent/guardian and caregiver links require authority reference, future expiry and guardian-document or court-order verification. Legal-representative links require court-order verification.
- Links are hospital-scoped, may be revoked, and expired/revoked/pending links cannot access records.
- A unique open-link constraint prevents duplicate pending/active links while allowing a new request after revocation.

## API
- `POST /api/v1/auth/patient-token`
- `POST /api/v1/patient-portal/links` — staff creates pending link.
- `GET /api/v1/patient-portal/links`
- `POST /api/v1/patient-portal/links/{link_id}/verify`
- `POST /api/v1/patient-portal/links/{link_id}/revoke`
- `GET /api/v1/patient-portal/patients`
- `GET /api/v1/patient-portal/patients/{patient_id}`
- `GET /api/v1/patient-portal/patients/{patient_id}/encounters`
- `GET /api/v1/patient-portal/patients/{patient_id}/lab-results`
- `GET /api/v1/patient-portal/patients/{patient_id}/medications`
- `GET /api/v1/patient-portal/patients/{patient_id}/invoices`
- `GET /api/v1/patient-portal/patients/{patient_id}/consents`
- `GET /api/v1/patient-portal/links/{link_id}/access-history`

## Access scope and clinical safeguards
Each link grants a bounded list of scopes: `profile`, `encounters`, `lab_results`, `medications`, `invoices`, `consents`. Each endpoint enforces its matching scope and the authenticated user's active, unexpired link. Laboratory results are limited to final results; critical results remain withheld until clinician acknowledgement. Draft invoices are hidden. Medication orders are read-only. Consent records can be viewed but not granted, altered or withdrawn through this module.

## Audit and tenant isolation
All link lifecycle changes emit standard audit events. Sensitive patient reads emit append-only access events with the link, user, patient, action and result count. RLS protects link and access-event tables; patient links have composite hospital/patient constraints. Patient-token authentication checks the active hospital and a current verified link before issuing a token. Patient portal access does not require or grant staff membership.

## Boundaries
No user signup, OTP delivery, MFA challenge, appointment booking, secure messaging, payment processing, medical-record amendment, consent management, inter-hospital record exchange or live external identity verification is included. These require Phase 4 integrations or dedicated workflows. Proxy authority is manually verified against protected evidence; the system does not independently adjudicate legal authority.

## Phase 5 verification
Automated tests are deferred to the central Phase 5 campaign. Verify token issuance, link verification/revocation/expiry, proxy authority, scope enforcement, final/critical laboratory visibility, billing privacy, tenant RLS, access-event immutability, concurrent duplicate links and re-linking after revocation.
