# Phase 2B.9 — AI evaluation and clinical release gates

## Purpose and safety boundary

A working model, passing software tests, a valid citation token, or a high aggregate score is not evidence of clinical safety. This milestone introduces a fail-closed evaluation contract for a specific capability + model version + prompt version + operating mode + dataset version tuple.

This is a governance and engineering control, not clinical certification. Clinical use remains disabled. No capability is automatically enabled by creating a successful evaluation or release record.

## Evaluation data governance

- Evaluation datasets must be synthetic or formally de-identified, versioned, checksummed, and approved for the intended evaluation purpose.
- Do not copy production patient records into evaluation fixtures. No real patient data, secrets, or identifiable case narratives belong in the repository.
- Dataset provenance, jurisdiction, license/permission, de-identification method, approval owner, approval date, and retention/deletion terms must be retained in the controlled evaluation registry before operational use.
- A dataset approval must be revocable. Revocation invalidates release eligibility for releases that depend on it.
- Maintain separate training, tuning, validation and held-out test splits. Prevent patient/source leakage across splits, even for de-identified records.
- Evaluation cases must be reviewed by qualified domain professionals and cover routine, edge, rare, emergency, ambiguous, incomplete and adversarial inputs.

## Required evaluation dimensions

Each run must report normalized scores from 0.0 to 1.0 for every dimension below. Threshold values are capability- and mode-specific; the initial code requires a complete threshold set but deliberately does not prescribe clinical cut-offs.

1. Factual support by approved evidence.
2. Citation integrity and source attribution.
3. Omission sensitivity, including clinically material missing facts.
4. Uncertainty calibration and appropriate abstention.
5. Red-flag sensitivity for urgent/emergency patterns.
6. False-alarm control and unnecessary escalation.
7. Subgroup performance and disparity analysis.
8. Prompt-injection resistance, including malicious instructions inside retrieved documents.
9. Tenant isolation and cross-hospital data leakage resistance.
10. Role, consent and purpose-of-use boundary enforcement.
11. Audit completeness and traceability.

For safety-critical dimensions, report denominators, confidence intervals, severity-weighted errors and worst-case slices in addition to aggregate scores. Do not allow a high aggregate to mask a critical miss. Define capability-specific hard-stop tests and minimum sample sizes through clinical governance before any production evaluation.

## Version-pinned evaluation runs

Every run binds immutable identifiers/digests for:
- capability and operating mode;
- provider, model identifier, model version and model artifact SHA-256;
- system/developer prompt and tool-policy versions;
- evaluation dataset ID, version and SHA-256;
- evaluator/harness version and SHA-256;
- threshold-set version;
- run timestamp, execution environment and result artifact.

A change to any bound artifact requires a new evaluation. Do not reuse approvals after a model, prompt, dataset, evaluator, policy, retrieval index or runtime change unless a documented impact assessment explicitly permits it.

## Release approvals and separation of duties

Release approval requires all of the following:
- complete evaluation suite and all thresholds passed;
- approved dataset and reproducible result artifacts;
- independent clinical safety owner approval;
- separate credential-verified clinical reviewer approval;
- approvals bound to the exact release and evaluation version;
- unexpired approvals and release window;
- no active revocation, unresolved critical incident or outstanding hard-stop failure.

The model developer, dataset submitter, evaluator operator, safety owner and clinical reviewer should be distinct wherever feasible. The code currently enforces distinct safety-owner and clinical-reviewer actor IDs, their expected roles, credential verification, approval timing and expiry. A trusted identity/credential registry and durable database-backed approval workflow are still required.

## Revocation, expiry and rollback

- Release approvals expire and must be renewed.
- Revoke a release immediately on a critical safety incident, dataset withdrawal, compromised artifact, material model/prompt/policy change, discovered subgroup harm, or loss of required regulatory/clinical authorization.
- Roll back to the last independently approved release, not merely the previous deployed model.
- Keep an immutable append-only record of evaluation runs, approvals, revocations, deployment activations and rollbacks.
- A revoked or expired release must not be newly activated. Existing deployments require a controlled disable/rollback action and audit event.

## Runtime integration policy

The current AI request master switch and per-capability allow-list remain disabled by default. This phase does not connect evaluation records to runtime activation, and it does not create a clinical enablement API. The in-memory gate contracts are groundwork for a subsequent persistence, authorization and deployment-control milestone. No model may be considered clinically approved based solely on these Python objects.

## Offline and hybrid operation

Evaluation is required separately for hosted and local providers, and separately for connected, offline and degraded modes where the capability is intended to operate. Offline evaluation must verify stale-knowledge handling, package signatures, knowledge expiry, identity/authorization freshness, revocation behavior, sync replay/idempotency and safe abstention when required evidence is unavailable. A full offline requirement does not waive release criteria or permit unapproved clinical behavior.

## Current implementation and outstanding work

Implemented in this milestone:
- typed metric taxonomy and complete threshold contract;
- version-pinned evaluation manifest and run;
- dataset safety approval flag and required approval identifier;
- fail-closed threshold comparison;
- separate safety-owner and clinical-reviewer approvals;
- credential, role, expiry, revocation and separation-of-duties checks;
- unit tests for pass/fail and approval failures.

Still required before operational clinical release:
- durable database models and Alembic migration for datasets, manifests, runs, thresholds, approvals, release records, revocations and deployment attestations;
- authenticated administrative APIs with fine-grained RBAC and credential registry integration;
- independent evaluation runner, signed result artifacts and reproducibility controls;
- clinical governance defining capability-specific thresholds, sample sizes, confidence bounds and hard-stop cases;
- dataset approval/revocation workflow and artifact/license registry;
- deployment controller that verifies release state and pinned artifact digest before activation;
- append-only, tamper-evident audit trail, monitoring, incident response and rollback automation;
- privacy, security, legal, regulatory and clinical safety review.

No real clinical content is seeded. No clinical capability is enabled. No patient-care use is authorized.
