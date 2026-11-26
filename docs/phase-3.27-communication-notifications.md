# Phase 3.27 — Communication & Notifications

## Objective
Provide a tenant-isolated, auditable communication orchestration layer for hospital users and patients. This module manages notification intent, consent, recipient eligibility, templates and provider-neutral delivery state. It does not itself integrate external messaging gateways.

## Functional scope
- User-managed channel preferences, opt-outs, locale, timezone and quiet-hour settings.
- Purpose-scoped patient channel consent, with consent revalidation before dispatch.
- Hospital-owned recipient groups with explicit role and department scopes.
- Versioned, reviewed templates with allow-listed placeholders and content classification.
- Idempotent notification intents and bounded dispatch queues.
- Delivery attempts, retry scheduling, provider acknowledgements and terminal failure handling.
- Patient-visible notification history and staff-scoped operational queue views.
- Append-only event history and minimal audit metadata.

## Security and privacy invariants
- Hospital RLS on every tenant-owned table and composite tenant foreign keys.
- Recipient eligibility is checked at enqueue and immediately before dispatch.
- A patient-facing notification requires an active, purpose-matched channel consent; opt-out or withdrawal blocks future dispatch.
- Message bodies are not copied into audit events. Default templates exclude direct identifiers and clinical narrative.
- Template publication and delivery administration are separate privileges; a template author cannot approve their own sensitive template.
- Delivery is not marked successful until a provider acknowledgement is recorded.
- Idempotency keys prevent duplicate logical messages; retries are bounded and safe.
- No clinical decision, triage, emergency dispatch or autonomous care action is performed.

## Workflow states
`queued` → `processing` → `delivered`; failures may move to `retry_scheduled` and return to `queued`, or end in `failed`. Authorized cancellation is allowed only before provider acceptance. Every transition records actor/system identity, timestamp and minimal metadata in an append-only event ledger.

## Phase 3 / Phase 4 boundary
Phase 3 implements local data models, APIs, authorization, consent checks, queue state and provider-neutral attempt records. Phase 4 connects verified patient contact points, SMS/email/push gateways, in-app delivery, appointment and telemedicine event publishers, localization and signed delivery webhooks. External provider credentials and network delivery are not enabled in Phase 3.

## UI requirements
- Communications administrator: template review/publishing, queue health, failed-delivery worklist and aggregate delivery metrics.
- Department manager: scoped operational notices and department queue visibility.
- Staff member: personal preferences, relevant notifications and delivery status.
- Patient: channel preferences, consent/opt-out controls and own notification history.

## Verification
All authorization, RLS, consent, idempotency, concurrency, retry, privacy and lifecycle scenarios are recorded in `docs/TEST_REGISTER_PHASE_5.md`. Backend tests remain deferred to Phase 5 by project direction.


## Implemented foundation (Phase 3.27)
- SQLAlchemy models and migration 0044_notifications for preferences, versioned templates, notification intents, delivery attempts and append-only events.
- Hospital RLS on all five tables; tenant-scoped composite foreign keys for templates, patient references, consent references and delivery history.
- User-owned staff and patient portal preferences, including channel opt-outs, locale, timezone and paired quiet-hour settings.
- Communications-admin template creation and publication; sensitive templates require a second authorized publisher and explicit approval.
- Idempotent enqueue API, recipient validation against same-hospital active membership or active patient portal link, purpose-matched unexpired patient consent and channel-specific consent scope.
- Patient/staff inbox reads, template/queue administration and cancellation before dispatch.
- Provider-neutral queue only: no external network call is made and queued items are not represented as delivered.

## API surface
- GET/PUT /api/v1/notifications/preferences
- GET/PUT /api/v1/notifications/patient/preferences
- POST /api/v1/notifications/templates
- GET /api/v1/notifications/templates
- POST /api/v1/notifications/templates/{template_id}/publish
- POST /api/v1/notifications/enqueue
- POST /api/v1/notifications/enqueue-department (optional role filter; locale-aware template selection)
- GET /api/v1/notifications/queue
- GET /api/v1/notifications/dashboard
- POST /api/v1/notifications/{intent_id}/cancel
- GET /api/v1/notifications/my-notifications
- GET /api/v1/notifications/inbox
- GET /api/v1/notifications/{intent_id}/events (staff recipient or communications administrator)
- GET /api/v1/notifications/patient/{intent_id}/events (patient portal recipient)

## Remaining within Phase 3
- Integrate the provider-neutral claim/result service with a scheduled worker runner when Phase 4 delivery adapters are introduced.

Backend verification remains deferred to Phase 5 per project direction. External SMS/email/push delivery and appointment/telemedicine publishers remain Phase 4.


## Queue lifecycle implementation
The notification service exposes provider-neutral claim and result-recording operations. Claims use row-level skip-locked semantics, revalidate recipient membership/portal linkage, consent and channel preference immediately before dispatch, defer quiet-hour messages, and recover stale processing claims after a bounded lease window. Retry scheduling uses bounded exponential backoff and terminal failure at the configured attempt ceiling. The service marks an intent delivered only when the adapter reports provider acknowledgement. Phase 4 adapters must use the notification intent UUID/idempotency key as the provider-side idempotency token to make stale-claim recovery safe against duplicate sends.


## Additional hardening
- Idempotency-key reuse with a different recipient, template, patient, consent or purpose is rejected with HTTP 409 rather than returning an unrelated existing intent.
- Patient portal recipient links are checked for expiry during enqueue; worker-side revalidation remains mandatory before dispatch.
- Staff and patient inbox payloads include the rendered title/body, while event-history endpoints expose only event type and timestamp to the recipient or an authorized communications administrator.
- Migration 0044 is a single clean Alembic revision with paired quiet-hour validation, five hospital-RLS tables, tenant-aware foreign keys and append-only attempt/event triggers.


## Department, locale and dashboard implementation
- Communications administrators can fan out a published template to active members of one department, optionally restricted to a hospital role. Recipients are selected from active same-hospital memberships and active user accounts; disabled channels are skipped.
- Fan-out uses a stable per-recipient idempotency digest so retrying a department send does not create duplicate logical notifications.
- Templates are versioned independently by locale. Department fan-out selects the newest published template matching each recipient's locale and falls back to the selected base template when a localized variant is unavailable or incompatible.
- The communications dashboard returns hospital-scoped aggregate counts by lifecycle state and channel; it does not expose message bodies or recipient identities.
