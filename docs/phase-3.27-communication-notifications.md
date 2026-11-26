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
