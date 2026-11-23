# Phase 2B.12 — Durable offline synchronization

## Purpose

Persist the offline node's knowledge installation state and synchronization lifecycle so that disconnected hospitals can exchange signed events safely and reconcile after connectivity returns.

## Implemented persistence

- Hospital-scoped offline knowledge installation records with snapshot version, digest, signing key, jurisdiction, issue/expiry timestamps, encrypted object-storage reference and lifecycle status.
- Per-hospital, per-source, per-stream monotonic synchronization cursors.
- Inbound event metadata with unique event identity and unique sequence constraints.
- Explicit conflict records for sequence gaps, sequence collisions, stale replays and event identity/digest mismatches.
- Outbound delivery outbox with idempotency key, encrypted payload reference, attempt count, retry schedule, status and partner acknowledgement reference.
- Forced PostgreSQL RLS on every table using the authenticated hospital context.

## Transactional service contract

- Incoming events are metadata-validated and queued only when they are exactly the next expected sequence.
- Gaps and collisions are persisted as conflicts and never silently skipped.
- Repeated identical event submissions are idempotent; reuse of an event ID with a different digest is a conflict.
- Domain changes and cursor advancement must occur in one database transaction through the supplied apply callback.
- Inbound acknowledgement is recorded only after the event is durably applied.
- Outbound deliveries are idempotent by hospital, destination and key.
- Workers claim due deliveries using row locks with SKIP LOCKED.
- Retry attempts are bounded; errors are stored as short codes, not raw payloads.
- An outbound delivery is marked delivered only from the sending state after the transport adapter has cryptographically verified a partner acknowledgement and supplied its reference.

## Data handling and operational boundary

Clinical payload bytes are not stored in these relational tables. They are referenced through encrypted object-storage identifiers. The object-storage encryption, access policy, retention and malware/archive scanning must be provisioned by platform operations.

The service functions do not commit transactions. The caller owns commit/rollback so that domain writes and cursor movement remain atomic. Concurrent creation of a first cursor can race on its unique key; the worker/API layer must retry the transaction on a uniqueness conflict.

This milestone does not implement partner discovery, transport adapters, FHIR payload mapping, offline identity reconciliation or a clinical record merge policy. It does not mark partner delivery complete without an acknowledgement. No live hospital sync is configured.
