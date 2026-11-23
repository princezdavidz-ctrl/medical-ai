# Phase 2 — Central AI operator runbook

## 1. Release posture

The system is an engineering foundation and clinical decision-support platform prototype. It is not approved for live patient care. Keep:
- `AI_REQUESTS_ENABLED=false`;
- `AI_ENABLED_CAPABILITIES=[]`;
- hosted provider disabled until transfer, privacy, legal and security approval;
- patient-context capability disabled until all authorization and clinical governance gates are complete.

Never load real patient records into development or evaluation environments.

## 2. Required infrastructure

- PostgreSQL 16 or compatible supported PostgreSQL release with RLS enabled.
- Redis for application readiness and supporting application services.
- TLS termination, restricted network paths, secrets manager and encrypted backups.
- Dedicated application database identity with least privilege; separate trusted governance/worker identities for privileged knowledge publication and other controlled jobs.
- A local model runtime for offline capability. Hosted inference is optional and requires explicit approval.

## 3. Database rollout

1. Back up the database and verify restore procedures.
2. Review migration diff and deployment change window.
3. Apply Alembic migrations through the current head using the migration identity.
4. Verify table ownership, RLS policies, forced RLS and application-role grants.
5. Confirm the application role cannot write governance approvals or bypass tenant boundaries.
6. Do not use `create_all` as the production schema migration mechanism.

The current migration head includes AI usage, evaluation prompt digest and hospital AI emergency control migrations. Confirm the exact head from the deployed repository revision before rollout.

## 4. Secrets and configuration

Configure secret values through the deployment secret manager, never source control or plain logs.

Relevant settings include:
- `SECRET_KEY` — unique high-entropy production JWT signing secret.
- `DATABASE_URL`, `REDIS_URL`.
- `AI_REQUESTS_ENABLED` — keep false until formal release.
- `AI_ENABLED_CAPABILITIES` — empty until each capability is independently approved.
- `AI_OPERATING_MODE` — hybrid/offline/degraded, consistent with the site connectivity policy.
- `AI_LOCAL_MODEL_ENABLED`, `AI_LOCAL_MODEL_BASE_URL`, `AI_LOCAL_MODEL_NAME`, `AI_LOCAL_MODEL_VERSION`, `AI_LOCAL_MODEL_DIGEST`, `AI_LOCAL_MODEL_ALLOWED_HOSTS`.
- `AI_HOSTED_MODEL_ENABLED`, `AI_HOSTED_DATA_TRANSFER_APPROVED`, `AI_HOSTED_MODEL_BASE_URL`, `AI_HOSTED_MODEL_NAME`, `AI_HOSTED_MODEL_VERSION`, `AI_HOSTED_MODEL_API_KEY`, `AI_HOSTED_MODEL_ALLOWED_HOSTS`.
- `AI_MODEL_PRICING_JSON` — exact operator-approved price rates and currency; never invent a local-model cost.
- `AI_USAGE_RESERVATION_TTL_SECONDS`.
- `AI_SESSIONS_ENABLED`, `AI_SESSION_ENCRYPTION_KEYS`, `AI_SESSION_ACTIVE_KEY_VERSION`, `AI_SESSION_RETENTION_DAYS`.

Production local model configuration requires a pinned version and SHA-256 digest. Hosted configuration requires HTTPS, an allow-listed host, a secret-backed API key and explicit data-transfer approval.

## 5. Startup and readiness

1. Start PostgreSQL and Redis.
2. Start the API with the reviewed release image.
3. Check `GET /api/v1/health/live`.
4. Check `GET /api/v1/health/ready`.
5. Authenticate as a hospital administrator and check `GET /api/v1/ai/operations`.
6. Confirm configured provider health, offline package expiry and sync queues. Do not interpret a healthy provider as clinical approval.

## 6. Provider and operating-mode rules

- Register only explicitly configured providers.
- Hybrid routing uses the policy-selected provider class.
- Offline/degraded must use local runtime only.
- Patient context must never be sent to hosted providers.
- Never introduce automatic cross-class fallback during incident response.
- A provider health failure should leave requests unavailable; do not bypass the policy gate.

## 7. Knowledge and offline operation

- Only publisher-signed, digest-verified, schema-compatible, jurisdiction-allowed and fresh packages may enter the controlled offline import pipeline.
- Offline knowledge still requires source licensing, reviewer credential checks and independent publication approval.
- Inspect `offline_knowledge` status and expiry in the operations dashboard.
- Inspect inbound queued/conflict counts, outbound queued/sending/failed counts and open conflicts.
- Do not manually mark a delivery complete without a verified partner acknowledgement.
- Offline queue and conflict metrics are operational indicators; they do not prove clinical data synchronization is complete.

## 8. Usage and subscription

- Provision a hospital usage policy only through the trusted platform billing workflow.
- Configure exact model pricing only when supported by an authoritative provider contract or measured local infrastructure cost.
- `GET /api/v1/ai/usage` is restricted to finance/admin roles.
- Requests fail closed when there is no active policy, ambiguous policy, or exceeded quota.
- Monitor estimated versus provider-reported token counts and unresolved expired reservations.

## 9. Emergency pause and recovery

To pause a hospital:
`PUT /api/v1/ai/operations/control` with `{"paused": true, "reason": "..." }`.

To resume after incident review:
`PUT /api/v1/ai/operations/control` with `{"paused": false, "reason": "..." }`.

Pause/resume is hospital-scoped and audited. Resuming does not override global execution disablement, capability approvals, provider configuration, subscription quotas or clinical release gates.

## 10. Incident response

- Pause affected hospital AI immediately.
- Preserve audit records, deployment SHA, provider/model version and prompt digest.
- Do not export prompts, patient identifiers or clinical context into tickets or logs.
- Revoke affected credentials or model release approvals through the authorized process.
- Investigate data isolation, provider routing, evidence provenance and offline synchronization.
- Resume only after incident owner sign-off; keep clinical use disabled pending independent review.

## 11. Phase 5 validation

All integration, migration, security, model, clinical, offline, load, backup/restore and recovery tests are listed in `docs/TEST_REGISTER_PHASE_5.md`. Do not mark any item passed without recorded evidence, environment, build SHA, reviewer and execution date.
