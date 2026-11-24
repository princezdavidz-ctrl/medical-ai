# Phase 3.14 — Insurance & Claims

## Implemented scope

This milestone adds hospital-scoped insurance administration and manual claims workflow records. It supports Kenya SHA and private insurer records as payer categories, without pretending to connect to any payer.

### Insurer catalog
- Hospital-scoped insurer definitions with code, name and payer type (`kenya_sha`, `private`, `employer`, `other`).
- New definitions start as draft and require independent finance/insurance administrator approval.
- Approval and retirement are separate governed states; retired definitions cannot be used for new coverage records.

### Patient coverage
- Coverage records link a hospital patient to an approved insurer.
- Member number, optional policy number, principal-member details and coverage dates are recorded.
- Coverage starts as reported; authorized staff record verification reference and verifier attribution before it can support a claim.
- The verification reference is an opaque manually entered reference. It is not proof of a live payer eligibility check.

### Claim workflow
- A claim is linked by composite tenant constraints to the same patient, encounter, verified coverage and issued invoice.
- Claimed amount cannot exceed the invoice subtotal; currency must match.
- Workflow: draft → submitted → accepted / partially approved / rejected → partially paid / paid.
- Submission records a payer-side reference entered by staff. Adjudication and payment receipt are separate manually recorded actions.
- Claim status events are append-only and preserve actor, transition, timestamp and a limited note.
- Role checks separate general claims staff from insurer/finance verifiers.

## API surface

- `POST /api/v1/insurance/insurers`
- `POST /api/v1/insurance/insurers/{insurer_id}/approve`
- `POST /api/v1/insurance/coverages`
- `POST /api/v1/insurance/coverages/{coverage_id}/verify`
- `POST /api/v1/insurance/claims`
- `POST /api/v1/insurance/claims/{claim_id}/submit`
- `POST /api/v1/insurance/claims/{claim_id}/adjudicate`
- `POST /api/v1/insurance/claims/{claim_id}/payments`

## Security and data boundaries

- All tables are hospital-scoped and use PostgreSQL row-level security.
- Composite foreign keys prevent cross-hospital patient, encounter, coverage and invoice linkage.
- Claims events are append-only at the database layer.
- Patient-care roles do not receive unrestricted claims/finance access.
- Coverage identifiers and claim references are sensitive data; API responses and audit records must remain purpose-limited.

## Explicit exclusions

- No live SHA, private insurer, broker or third-party payer API.
- No real-time eligibility or benefit-limit verification.
- No preauthorization, e-claim transmission, payer adjudication, remittance-file ingestion or automatic reconciliation.
- No automatic claim generation from clinical records.
- No live patient data, real member identifiers or production payer credentials.
- No guarantee that a manually recorded claim submission, adjudication or payment occurred externally.

All external SHA/private-insurer workflows are deferred to Phase 4 and must use verified partner specifications and credentials. All validation cases are registered in `docs/TEST_REGISTER_PHASE_5.md`; tests have not been executed in this milestone.
