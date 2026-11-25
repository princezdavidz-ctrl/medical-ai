# Phase 3.22 — Patient Portal

## Scope
A hospital-scoped patient self-service API for verified patient and proxy accounts. It exposes only the patient records explicitly granted by an active portal link: demographics, encounters, finalized laboratory results, medication orders, invoices and consent records. Sensitive reads are recorded in an immutable access-event ledger.

## Identity and access
1. A portal user must already have an active user account. This module does not create user accounts or implement email OTP delivery; account registration and OTP integration are Phase 4 work.
2. Hospital medical-records staff or a hospital administrator creates a pending link between an existing user and a patient record. The module does not automatically match users to patients using MRN, date of birth or phone number.
3. A different authorized staff member must independently verify the pending link using in-person, identity-document, verified-email or verified-phone evidence stored by protected vault reference.
4. Parent/guardian and caregiver links require an authority reference, expiry timestamp and guardian-document or court-order verification. Legal-representative links require court-order verification.
5. Patient portal token issuance requires valid user credentials, an active hospital and an active verified link. MFA-enabled users are denied until the dedicated MFA challenge flow is available.
6. Every request rechecks active link status and expiry. Revoked and expired links cannot access patient data.

## Access scopes
Allowed scopes are `profile`, `encounters`, `lab_results`, `medications`, `invoices` and `consents`. New links default to the least-privilege `profile` and `encounters` scopes; staff must explicitly grant any additional categories. Proxy links are time-limited. All data reads are tenant-filtered by hospital and patient and recorded with the link, user, action, resource count and timestamp.

## API
- `POST /api/v1/auth/patient-token`
- `POST/GET /api/v1/patient-portal/links`
- `POST /api/v1/patient-portal/links/{link_id}/verify`
- `POST /api/v1/patient-portal/links/{link_id}/revoke`
- `GET /api/v1/patient-portal/links/{link_id}/access-history`
- `GET /api/v1/patient-portal/patients`
- `GET /api/v1/patient-portal/patients/{patient_id}`
- `GET /api/v1/patient-portal/patients/{patient_id}/encounters`
- `GET /api/v1/patient-portal/patients/{patient_id}/lab-results`
- `GET /api/v1/patient-portal/patients/{patient_id}/medications`
- `GET /api/v1/patient-portal/patients/{patient_id}/invoices`
- `GET /api/v1/patient-portal/patients/{patient_id}/consents`

## Clinical and privacy safeguards
- Only finalized laboratory results are exposed. Critical results are withheld until a clinician acknowledgement exists.
- Invoice drafts are never exposed.
- Proxy access is explicit, scoped and expiring; a caregiver link does not imply authority to consent to treatment.
- Portal reads are logged; access-event records are append-only.
- No cross-hospital records are exposed through this portal. Inter-hospital sharing remains request-based and consent-gated.
- Password-only token issuance is disabled for MFA-enabled accounts.

## Boundaries
No patient account signup, OTP delivery, MFA challenge, appointment booking, secure messaging, telemedicine, bill payment, document upload, prescription refill requests, clinical advice, discharge-plan workflow or cross-hospital record exchange is included. Phase 4 must connect account signup/OTP, appointment settings and any additional portal workflows to their respective services.

## Phase 5 verification
Automated tests are deferred. Validate independent identity verification, proxy authority and expiry, token issuance, scope enforcement, tenant isolation, critical-result release rules, invoice filtering, revocation, access logging and database immutability.
