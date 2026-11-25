# Phase 3.1B — Patient consent and declared lawful-basis workflow

## Purpose

Record purpose-specific patient processing authorization with a narrow data scope, declared basis, evidence reference and reviewer history. This is a recordkeeping and policy-enforcement primitive, not a legal determination that a selected basis is valid under Kenyan law or another jurisdiction.

## Request scope

Each request records:
- purpose code: care delivery, care coordination, referral, billing, insurance claim, patient portal, record sharing or other;
- explicit data categories (demographics, contact details, clinical records, lab results, imaging, medications, billing, insurance or other);
- explicit permitted uses, including record_sharing when disclosure is requested;
- declared basis code;
- optional timezone-aware expiry.

The declared purpose must be included in permitted uses. The record_sharing purpose must also include the actual release use (for example referral or care coordination) in permitted uses. Research use is not enabled by this workflow.

## Declared basis codes

- `patient_consent`
- `guardian_consent`
- `healthcare_provision`
- `vital_interests`
- `legal_requirement`
- `other_lawful_basis`

These are structured declarations for governance and policy checks. Legal counsel must map and approve them against the applicable law, hospital policy, patient category and actual processing purpose before production use.

## Decision lifecycle

1. A records verifier creates a pending request. The actor and scope are recorded.
2. A pending request can be granted or rejected.
3. Grant requires an opaque `vault://` UUID evidence reference and a consent method matching the declared basis:
   - patient consent: written, electronic or verbal;
   - guardian consent: guardian;
   - other declared bases: not applicable.
4. Grant records the reviewer, evidence reference, method and timestamp.
5. A granted authorization can be withdrawn by an authorized records verifier; withdrawal actor, time and reason are recorded.
6. Rejected and withdrawn records are terminal. A new request is required for a new decision.
7. Expired grants are reported as `effective_status=expired` and are excluded from authorization checks.

Raw consent documents, signatures, recordings and identity details are not stored in the consent table. Only an opaque encrypted-vault reference is retained.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/patients/{patient_id}/consents` | Create a pending purpose/scope/basis request |
| GET | `/api/v1/patients/{patient_id}/consents` | Read consent history and effective status |
| PATCH | `/api/v1/patients/{patient_id}/consents/{consent_id}/decision` | Grant, reject or withdraw |

Only medical records officers, hospital administrators/directors and system administrators may create or decide these records.

## Reusable authorization service

`app.services.patient_authorization.has_active_patient_authorization` returns true only when one current, granted, non-withdrawn, unexpired record covers:
- the exact purpose;
- every requested data category;
- the requested permitted use.

A downstream patient-data exchange, referral, portal or other module must call this service before disclosing or processing data under a consent-based authorization. The service fails closed on malformed scope data.

## Important limitations

- This workflow records a declared lawful basis; it does not certify its legal validity.
- A vault storage provider and authorized evidence retrieval process must be deployed before any real consent artifacts are used.
- The service is available for downstream modules but has not yet been wired into every future data access or HIE endpoint.
- Emergency access and lawful exceptions require their own narrowly scoped, audited workflows.
- No consent is inferred from patient registration, next-of-kin details or a prior unrelated purpose.
- No real patient data is approved for development.

All consent, scope, expiry, withdrawal, RLS, role, evidence and downstream authorization tests are in the Phase 5 Test Register.
