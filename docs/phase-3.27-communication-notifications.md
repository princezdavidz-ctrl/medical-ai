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
- GET /api/v1/notifications/queue
- POST /api/v1/notifications/{intent_id}/cancel
- GET /api/v1/notifications/my-notifications
- GET /api/v1/notifications/inbox

## Remaining within Phase 3
- Add a bounded dispatcher/worker lifecycle with safe claim locking, retry scheduling, dead-letter handling and provider acknowledgement contract.
- Add department-scoped notice publishing and granular recipient audience resolution.
- Add localized template rendering and timezone-aware quiet-hour scheduling.
- Add operational metrics and staff-facing dashboard surfaces.

Backend verification remains deferred to Phase 5 per project direction. External SMS/email/push delivery and appointment/telemedicine publishers remain Phase 4.


## Queue lifecycle implementation
The notification service exposes provider-neutral claim and result-recording operations. Claims use row-level skip-locked semantics, revalidate recipient membership/portal linkage, consent and channel preference immediately before dispatch, defer quiet-hour messages, and recover stale processing claims after a bounded lease window. Retry scheduling uses bounded exponential backoff and terminal failure at the configured attempt ceiling. The service marks an intent delivered only when the adapter reports provider acknowledgement. Phase 4 adapters must use the notification intent UUID/idempotency key as the provider-side idempotency token to make stale-claim recovery safe against duplicate sends.


## Department notices and dashboard (Phase 3.27 continuation)
- Department-scoped notice creation is available to hospital communications administrators and to department/nurse managers limited to their own active department.
- Recipient resolution is limited to active users with active membership in the same hospital and selected department; optional role filters narrow the audience.
- Each recipient receives a separately idempotent intent. Channel opt-outs are honored and counted without disclosing message content.
- Communications dashboard metrics aggregate queue counts by state and channel without exposing notification bodies or patient identifiers.
- Endpoints added: POST /api/v1/notifications/department-notices and GET /api/v1/notifications/dashboard.


## Localization and quiet-hour constraint correction (Phase 3.27 continuation)
- Notification templates now carry a validated locale and versions are unique per hospital, template code, locale and version.
- At enqueue, the recipient preference locale is selected; a published same-channel translation is preferred, with English fallback and then the explicitly selected base template.
- Department notices resolve the best published locale variant per recipient and preserve per-recipient idempotency and opt-out behavior.
- Migration 0045_notification_locales adds locale support without rewriting existing templates; existing rows default to English. Downgrade is guarded and refuses to discard localized versions.
- The quiet-hour database check expressions in migration 0044 and the ORM model are corrected to enforce valid 24-hour clock values.


## Recipient inbox read state
- Notification inbox responses now include the rendered title/body and read timestamp, visible only to the recipient or authorized hospital communications administrators.
- Staff and patient portal users can mark only their own notifications as read; patient routes are restricted to in-app notifications.
- Staff and patient dashboard endpoints expose total and unread counts without cross-user visibility.
- Migration 0046_notification_read_state adds the nullable read timestamp.


## Recipient event history and final hardening
- Staff recipients can retrieve lifecycle events only for their own notifications; patient portal recipients can retrieve events only for their own in-app notifications. Event payloads expose event type and timestamp, not internal metadata.
- Reusing an idempotency key with a different recipient, patient, consent, purpose or template code returns HTTP 409. Localized versions of the same template code remain idempotently equivalent.
- Patient portal links are checked for expiry both when enqueueing and immediately before dispatch.
