# Phase 2B.5 — Clinical knowledge review and publication

## Lifecycle

- Tenant submissions are untrusted proposals. Row-level security permits hospital users to INSERT import batches and staged payloads only; users cannot update batches or staged-document state.
- A platform-controlled ingestion process validates the declared license and source provenance, computes integrity hashes, and advances eligible documents into review.
- A reviewer must have an active, time-valid authorization provisioned by the trusted platform credential-verification process. Hospital reviewers must also hold active membership in the relevant hospital.
- The submitter cannot review their own submission.
- A distinct authorized publisher must publish an approved item. The publisher cannot be the submitter or approving reviewer.
- Publication rechecks source scope, active status, license metadata, staged payload SHA-256, current reviewer authorization and review deadline.
- Publication creates the approved knowledge document and its searchable chunk in one transaction.
- If a current approved version exists for the same source, publication must supersede exactly that version. The prior version is marked superseded in the same transaction; duplicate current versions are rejected. Source/version is unique.

## Reviewer credentials

The reviewer authorization record stores professional registration, credential type/reference, verifier identity, verification time, expiry, scope and status. Only a trusted platform credential-verification process may create, activate, suspend or revoke these authorizations. The code does not independently query a professional regulator; human verification evidence and platform administration controls are required before an authorization becomes active.

## Audit immutability

Review decisions are stored as append-only events. A PostgreSQL trigger rejects UPDATE and DELETE, including from privileged application workflows. Tenant RLS allows users to submit an event for their own import, but cannot write approval, rejection or publication decisions. Those decisions require the trusted review/publishing worker.

## Privileged worker boundary

The review and publication service is not exposed as a public API. It must run only under a separately managed platform worker database identity with the minimum required privileges and audited job invocation. Do not run it with ordinary tenant application credentials. Provisioning that worker identity, secrets, execution authorization, monitoring and operational approval is a deployment prerequisite.

Global knowledge intake and publication are reserved for platform-controlled processes. Tenant hospital users cannot create or mutate global records.

## Retrieval safety

Only approved, current knowledge documents with valid review deadlines remain eligible for retrieval. Staged documents and rejected items are never retrieved. Publication does not itself establish clinical suitability: each source and content item still requires jurisdiction-specific clinical review, evidence assessment and ongoing re-review.

## Not included

- No public review, approval, credential-management or publication API.
- No automatic regulator lookup or credential verification.
- No real clinical data, guidelines, reference intervals, drug doses or terminology catalog seeded.
- No clinical use authorization. This remains a governed software foundation and requires security, privacy, legal and clinical-safety review before production use.
