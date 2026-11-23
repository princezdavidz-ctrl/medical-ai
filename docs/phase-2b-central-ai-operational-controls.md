# Phase 2B.18 — Central AI operational controls

## Hospital operations dashboard

Authenticated hospital administrators, hospital directors and system administrators can read:
- configured local/hosted provider identity and live health-check result (without exposing endpoint URLs or secrets);
- global AI execution gate and approved capability allow-list;
- current/expired/revoked/failed offline knowledge installation summary;
- inbound offline event counts by state;
- outbound delivery counts by state;
- open offline synchronization conflicts;
- hospital-level emergency pause state.

The dashboard is hospital-scoped through the authenticated hospital context and PostgreSQL RLS. Viewing the dashboard writes a privacy-minimal audit event.

## Emergency pause control

`PUT /api/v1/ai/operations/control` accepts a boolean pause state and a required reason. Only hospital administrators, hospital directors and system administrators may change it.

- Pausing immediately blocks subsequent AI requests for that hospital with HTTP 503.
- Resuming removes the hospital-level pause but does not override the global AI execution gate, capability allow-list, provider policy, usage quotas or clinical release requirements.
- Every pause/resume action records actor, hospital, timestamp and reason in the audit log.
- The control record is protected by forced PostgreSQL RLS.

## Existing readiness endpoints

- `GET /api/v1/health/live`: process liveness.
- `GET /api/v1/health/ready`: database and Redis readiness.
- `GET /api/v1/ai/capabilities`: per-capability policy/provider status and prompt registry version/digest.
- `GET /api/v1/ai/usage`: hospital AI subscription usage (admin/finance role).
- `GET /api/v1/ai/operations`: provider, offline package, sync queue and pause status (admin role).
- `PUT /api/v1/ai/operations/control`: hospital-level emergency pause/resume.

## Safety and limitations

- Provider health checks contact only explicitly configured providers and return no secret or endpoint details.
- Offline installation and queue metrics are observational; this endpoint does not install packages, apply sync events or mark deliveries complete.
- The hospital pause is an emergency control, not a replacement for the global execution gate or independent clinical release approval.
- No automatic model fallback is introduced.
- AI remains disabled by default and clinical use remains false.
