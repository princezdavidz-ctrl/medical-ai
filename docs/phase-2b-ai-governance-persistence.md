# Phase 2B.10 — Persistent AI governance registry

## Scope

This migration adds durable metadata tables for evaluation datasets, capability/mode threshold sets, evaluation runs, model releases, independent release approvals and governance events. It stores metadata and scores, not raw evaluation prompts, clinical cases, patient records, or model artifacts.

## Database security boundary

All six tables have PostgreSQL row-level security enabled and forced. The only policy admits the dedicated database role named medical_ai_governance_worker. Ordinary hospital application sessions have no matching policy and therefore receive no rows and cannot write these records.

The governance worker role must be provisioned separately with least privilege. It must not be a superuser, must not have BYPASSRLS, and should receive only the table privileges needed for its specific jobs. The migration deliberately does not create credentials, grant broad privileges, or make the role available to the ordinary API process. Until the role and worker are deployed, the registry is intentionally inaccessible.

The append-only governance event table also has a database trigger rejecting UPDATE and DELETE. Dataset and release state changes must be represented by controlled state transitions and governance events; the event history itself cannot be rewritten by ordinary SQL updates.

## Stored records

- Dataset registry: synthetic/de-identified classification, SHA-256, provenance and license reference, submitter, approver, approval and revocation timestamps.
- Threshold sets: capability, operating mode, immutable version, metric thresholds and hard-stop rule metadata, with draft/approved/retired/revoked state.
- Evaluation runs: provider/model/version/digest, prompt version, evaluator version/digest, dataset and threshold-set references, metric/failure JSON, result digest and run status.
- Model releases: exact evaluation and threshold-set references, expiry, revocation, activation state and previous approved release pointer.
- Release approvals: one record per required role, actor, external credential reference, independent credential verifier, approval/expiry/revocation timestamps.
- Governance events: append-only actor/action/resource/outcome/reason and minimal metadata.

## Important constraints and limitations

- These tables are not exposed through the ordinary hospital API.
- The database does not independently prove that an external credential is genuine; the trusted governance worker must verify it against an approved credential source and record the verification reference.
- Database uniqueness/check constraints are necessary but do not replace application-level transition validation, signed evaluation artifacts, identity verification or clinical governance.
- No deployment activation endpoint exists. A future deployment controller must check the current release, run, dataset, threshold set, both approvals, expiry and revocation immediately before activation.
- No thresholds are seeded. Clinical cut-offs and hard-stop rules must be approved by qualified clinical governance, never guessed by developers.
- No patient data or clinical evaluation cases are included.
- Migration has not been executed against a live database in this change. Tests and migration rehearsal remain separate validation tasks.

## Next work

Provision the isolated governance database role and worker, then add authenticated administrative workflows with credential-registry integration, signed evaluation artifacts, immutable state-transition events, expiry/revocation checks and deployment activation/rollback controls. Keep the clinical AI master gate and per-capability allow-list disabled until independent release governance and all required reviews are complete.
