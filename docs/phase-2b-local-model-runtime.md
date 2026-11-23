# Phase 2B.7 — Local model runtime adapter

## Scope

Adds a provider adapter for an explicitly configured local OpenAI-compatible chat endpoint. It does not download, select, train or certify a medical model, and does not enable clinical capabilities.

## Runtime behavior

- Requests go only to the configured base URL's `/v1/chat/completions` endpoint.
- The provider sends the prompt and structured evidence context. Retrieved source material is explicitly marked as untrusted data.
- Streaming is disabled, temperature is fixed at zero, and output tokens, input characters and response characters are bounded.
- The server-reported model ID must exactly match the configured model name.
- A readiness check calls `/v1/models` and requires the exact configured model ID.
- Returned model identity includes configured version metadata and, when supplied, a shortened SHA-256 artifact digest.
- HTTP, timeout, invalid JSON, unexpected model identity and malformed response errors fail closed.
- The gateway never changes provider class or falls back from local to hosted.

## Configuration and network boundary

The runtime is disabled by default. Enabling it requires a base URL and exact model name. Every hostname must be explicitly present in `AI_LOCAL_MODEL_ALLOWED_HOSTS`. URLs cannot contain embedded credentials, path prefixes, query strings or fragments. Optional API keys are read from environment-backed secrets and are never logged.

Production configuration additionally requires a pinned model version and SHA-256 digest. The application records this identity but cannot attest the actual model files served by an arbitrary endpoint. Deployment must verify the artifact digest, runtime image, model manifest, network isolation and supply chain independently.

The inference endpoint should be on a private network, not exposed to the public internet. Restrict outbound access from the hospital API to the configured endpoint and deny all other model-provider egress unless separately approved.

## Offline and hybrid policy

This adapter registers only the local provider. It does not implement a hosted provider or fallback route. Offline/degraded mode continues to require the local provider and fails closed when it is unavailable. Hybrid routing uses the existing policy engine; patient-context requests cannot be sent to hosted models.

## Not included

- No Ollama or other inference server deployment, model download, training or fine-tuning.
- No model selection or clinical performance certification.
- No patient-context adapter, and no patient data is sent as a separate request field by this adapter.
- No hosted model integration, automatic failover, API endpoint wiring or clinical capability enablement.
- No clinical use approval. Each model/capability requires independent evaluation, monitoring, rollback and clinical governance.
