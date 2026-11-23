# Phase 2B.8 — AI request runtime wiring

## API execution path

Authenticated requests now flow through the central orchestrator, approved-knowledge retriever, provider-neutral gateway and configured local model provider. The application lifespan creates one gateway and closes provider resources during shutdown. The API returns validated evidence citation metadata alongside the model output.

## Safety gates

- `AI_REQUESTS_ENABLED=false` by default. No model request is executed until an operator explicitly enables this master gate.
- Individual capabilities remain disabled unless explicitly allow-listed.
- The local model provider must be configured and registered. No provider means a 503 response; no automatic fallback occurs.
- Requests containing a patient-context ID are rejected because the authorized patient-context adapter is not implemented.
- Hosted providers are not implemented in this milestone. The current runtime factory registers only the local provider.
- Responses with missing, malformed or unknown evidence citations are withheld and audited.
- AI prompts, generated content and patient identifiers are not written to audit metadata. Audit records contain capability, mode, provider/model identity and citation count only.
- Successful responses explicitly state that clinical use is not enabled and clinician review is required.

## Capability status

The capabilities endpoint distinguishes the master execution gate, capability approval, policy route and provider registration. A configured provider is not the same as a healthy or clinically validated model. Runtime readiness checks and evaluation gates remain separate.

## Current limitations

- No patient-context retrieval or patient-data access.
- No hosted provider, provider failover or external model routing.
- No persisted AI sessions, message history, feedback or usage accounting.
- No rate limiting, model monitoring, clinical evaluation suite or formal model release approval.
- The local runtime adapter does not attest model artifact integrity; deployment must independently verify the pinned model digest and runtime image.
- No clinical capability should be enabled for real patient care until clinical, privacy, security, legal and regulatory approvals are complete.
