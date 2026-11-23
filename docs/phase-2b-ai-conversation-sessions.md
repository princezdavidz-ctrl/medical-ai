# Phase 2B.15 — Encrypted AI conversation sessions

## Storage and ownership

- Conversation sessions are scoped to one hospital and one staff-user owner.
- PostgreSQL RLS checks both `app.current_hospital_id` and `app.current_user_id` for sessions and messages.
- A composite foreign key prevents a message from being attached to a session under a different hospital or owner.
- Session message content is encrypted using AES-256-GCM before it is written to PostgreSQL.
- Every message uses a fresh 96-bit nonce and authenticated additional data binding hospital, session, sequence, role and key version.
- Message metadata contains only limited provider/model/citation identifiers; prompts and responses are not stored in plaintext or audit metadata.

## Key management

The keyring is supplied through the secret-backed `AI_SESSION_ENCRYPTION_KEYS` setting as a JSON mapping of key-version labels to base64-encoded 32-byte keys. `AI_SESSION_ACTIVE_KEY_VERSION` selects the key for new messages. Previous key versions must remain available for decrypting older messages until those messages are purged.

No encryption key is seeded in the repository. Key generation, secure secret storage, access control, backup, rotation and destruction must be handled by deployment operations. Loss of an old key makes its ciphertext unreadable.

## API behavior

- `POST /api/v1/ai/sessions`: create a private session.
- `GET /api/v1/ai/sessions`: list the current user's active sessions.
- `GET /api/v1/ai/sessions/{session_id}`: decrypt and read an owned session.
- `DELETE /api/v1/ai/sessions/{session_id}`: delete encrypted messages and mark the session deleted.
- `POST /api/v1/ai/requests` accepts optional `session_id`; successful request/response turns are encrypted and appended atomically with the completion audit event.

Session persistence is disabled by default. It requires `AI_SESSIONS_ENABLED=true`, a valid keyring and an active key version. Session expiry is configured by `AI_SESSION_RETENTION_DAYS`.

## Privacy and retention

- Sessions are private to their creator; there is no shared/team session mode.
- Deletion removes message ciphertext rows and marks the session deleted.
- A bounded purge function deletes expired message ciphertext per authenticated hospital/user context; deployment must schedule this worker operation.
- The database stores no plaintext conversation content. Decrypted messages are returned only to the owning staff user.
- Patient context is not automatically persisted as a separate object; if a user submits identifiable content in a prompt, the prompt is encrypted at rest but still subject to the applicable patient-data consent and local-only routing rules.

## Limitations

- No session title editing, sharing, export archive, automated scheduled purge deployment or key-management integration is configured.
- The session feature is not enabled by default.
- This is not authorization for patient-care use; clinical AI remains disabled by default and responses still require clinician review.
