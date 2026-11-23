# Phase 2B.11 — Signed offline knowledge package security

## Purpose

Offline hospital nodes need a trusted way to receive approved knowledge snapshots without depending on a live network connection at query time. This milestone establishes package verification before any offline import or publication.

## Implemented contract

- Ed25519 publisher signatures over canonical manifest metadata.
- SHA-256 digest verification of the complete package payload.
- Signing-key identifier lookup against a pre-provisioned trusted public-key registry.
- Schema-version allow-list.
- Package identity and non-empty content checks.
- Issue-time, expiry-time and maximum-age enforcement.
- Jurisdiction allow-list enforcement.
- Monotonic sync event classification that distinguishes ready events, duplicates/stale events, sequence gaps and invalid events.

## Safety boundary

- Verification does not publish content, mark a knowledge source approved or bypass the knowledge review and publication workflow.
- No public keys or clinical content are seeded.
- The trusted key registry and rotation/revocation process must be provisioned by platform operations.
- Package payload schema validation, archive bomb protection, encrypted local storage, atomic install, durable cursor persistence and replay reconciliation are subsequent work.
- The sync classifier does not apply events or acknowledge delivery; durable application is Phase 2B.12.
- This is not a clinical knowledge certification or authorization to use unreviewed content.

## Dependencies

The backend now declares the cryptography dependency directly. The offline package verifier is isolated from the request-serving runtime until the package importer and trusted key management service are implemented.
