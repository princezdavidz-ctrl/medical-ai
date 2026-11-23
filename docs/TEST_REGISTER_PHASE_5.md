# Phase 5 — Central Test Register

This register collects verification work across all project phases. Development phases do not pause for test execution. Tests are run during the dedicated Phase 5 validation campaign, unless a safety-critical defect requires an immediate development correction.

## Current known CI finding

Source: GitHub Actions Backend CI run 45144650972 on commit 6307a0ec2b9ab969a926eeffd603cbb35a483af5.

- [ ] Re-run Ruff after the lint corrections in the Phase 2B.11 branch are merged.
- [ ] Confirm all lint checks are clean across app, tests and migrations.
- [ ] Run Alembic migrations from an empty PostgreSQL 16 database through head.
- [ ] Confirm the least-privileged application DB role can access only its intended tenant rows and cannot access governance tables.
- [ ] Execute the complete pytest suite. The run above stopped at lint, so migrations and pytest were skipped.
- [ ] Resolve any additional failures found after lint is clean.

The five lint findings were:
1. `app/ai/evaluation.py`: import `Mapping` from `collections.abc`.
2. `app/api/routes/ai.py`: remove unused `fastapi.status`.
3. `app/core/config.py`: combine nested production model validation conditions.
4. `app/models/__init__.py`: sort `__all__`.
5. `app/models/knowledge_ingestion.py`: remove unused `sqlalchemy.func`.

These corrections are included in the current development branch; they have not been re-validated.

## Backend and security

- [ ] Authentication, password hashing, JWT expiry, MFA enrollment/challenge/recovery and account recovery.
- [ ] Hospital and department RBAC, staff membership changes, role revocation and session expiry.
- [ ] PostgreSQL RLS tenant isolation for every tenant-owned table and bypass-resistance.
- [ ] Consent, purpose-of-use, emergency access, audit completeness and audit immutability.
- [ ] Encryption at rest/in transit, key rotation, secrets handling, backup restoration and disaster recovery.
- [ ] API rate limits, input validation, upload limits, dependency vulnerabilities and penetration testing.

## Central AI runtime

- [ ] Master execution gate and empty-by-default capability allow-list.
- [ ] Hosted/local provider routing, strict no-cross-class fallback and outage behavior.
- [ ] Hosted HTTPS-only endpoint, hostname allow-list, secret handling, model identity and timeout limits.
- [ ] Hosted transfer approval, public classification, identifier checks, and proof that patient context is never sent to hosted.\n- [ ] Public/sensitive input classification enforcement for local and hosted providers, plus direct-identifier rejection across all request paths.
- [ ] Offline/degraded provider routing never invokes hosted, even during local runtime failure.
- [ ] Offline and degraded mode: no network dependency, no accidental hosted calls.
- [ ] Model identity/version/digest pinning and artifact attestation.
- [ ] Approved-evidence retrieval, source freshness, jurisdiction filtering and tenant scoping.
- [ ] Citation token validation, citation-to-source accuracy and unsupported-answer abstention.
- [ ] Prompt injection in user prompts, retrieved documents and tool outputs.
- [ ] Context limits, timeouts, cancellation, concurrency, resource exhaustion and malicious payloads.
- [ ] Patient-context authorization, consent, purpose limitation and minimum-necessary access.
- [ ] Patient assignment creation/revocation, role allow-list, consent expiry/withdrawal and same-hospital encounter enforcement.
- [ ] Confirm patient context is never queried without a registered local provider and never routed to hosted models.
- [ ] Verify no direct identifiers or unredacted free-text notes enter model context.
- [ ] Clinical capability evaluations by capability, model, prompt, dataset and operating mode.
- [ ] Red-flag sensitivity, false alarms, uncertainty calibration, omissions and subgroup analysis.
- [ ] Governance worker role isolation, approval separation, expiry, revocation and rollback.
- [ ] Signed offline package tampering, unknown keys, expired packages, stale packages and jurisdiction rejection.
- [ ] Offline sync replay, duplicate events, sequence gaps, conflict resolution and reconnect reconciliation.
- [ ] Offline cursor concurrency, atomic apply/cursor commit, first-cursor race retry and RLS isolation.
- [ ] Outbox idempotency, SKIP LOCKED worker concurrency, bounded retries and verified partner acknowledgement.
- [ ] AI session retention, access controls, deletion/export and audit privacy.
- [ ] AES-GCM round trip, ciphertext tampering, AAD binding, key rotation and missing-key behavior.
- [ ] Database RLS owner isolation, composite session/message ownership, cross-hospital access and deletion.
- [ ] Session expiry, scheduled purge, append-turn atomicity and no plaintext prompt/response persistence.
- [ ] Bounded history reconstruction, truncation signaling, prompt-injection isolation and local-only session routing.
- [ ] Usage metering accuracy, tenant quotas, billing aggregation and fail-safe behavior.

## Clinical safety and interoperability

- [ ] Qualified clinical review of knowledge sources, reference ranges, medication safety rules and escalation rules.
- [ ] Validate that no unreviewed, expired or superseded knowledge is retrievable.
- [ ] Verify clinical decision support never represents itself as a diagnosis or autonomous order.
- [ ] Test emergency escalation, abstention and clinician handoff behavior.
- [ ] FHIR R4 conformance, partner identity matching, consent enforcement and request-based records exchange.
- [ ] Referral acceptance, bed confirmation, transport dispatch, arrival, handover and admission events.
- [ ] Offline facility queueing and reliable later synchronization.

## Hospital modules and integrations

- [ ] Each of the 40 modules: permissions, workflow, data integrity, audit, accessibility and usability.
- [ ] Module-to-API integration and cross-module workflows.
- [ ] Kenya SHA and private insurer claims workflows.
- [ ] Pharmacy, laboratory, radiology, medical devices, messaging and payment integrations.
- [ ] Performance/load, resilience, failover, backup restore and multi-hospital scale.

## Release readiness

- [ ] Privacy impact assessment, threat model, penetration test and remediation.
- [ ] Kenyan legal/regulatory review and applicable health-data compliance.
- [ ] Independent clinical safety case and signed release approvals.
- [ ] Disaster recovery and incident response exercise.
- [ ] Staged deployment, monitoring, rollback and operational sign-off.
- [ ] Explicit approval before any patient data or clinical AI is used in live care.

No item is considered passed until evidence, environment, build SHA, reviewer and execution date are recorded.
