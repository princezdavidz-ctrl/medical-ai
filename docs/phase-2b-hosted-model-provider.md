# Phase 2B.14 — Explicit hosted model provider

## Provider contract

The central Model Gateway now supports a hosted OpenAI-compatible provider that is registered only when both the hosted provider switch and explicit hosted data-transfer approval are enabled.

The provider requires:
- an HTTPS endpoint origin;
- an exact hostname in the administrator-configured allow-list;
- a secret-backed API key;
- an explicit model identifier and pinned provider model version;
- bounded timeout, token and response sizes;
- exact model identity in the response envelope.

Credentials are never written to logs. The provider does not retry through a local model or another hosted provider. The provider itself rejects offline and degraded operating modes.

## Routing and data boundaries

- Hosted routing remains disabled by default (`AI_ALLOW_HOSTED=false` and `AI_HOSTED_MODEL_ENABLED=false`).
- A separate `AI_HOSTED_DATA_TRANSFER_APPROVED` switch is required before the hosted provider can be registered.
- Patient-context requests are local-only and never route to hosted providers.
- Requests without an authorized patient-context ID must be explicitly classified `input_classification=public`; the default is `sensitive` and is rejected without authorized patient context, regardless of provider. Obvious direct identifiers are rejected from all free-text prompts.
- Hosted requests additionally require hybrid mode, public classification and no matches from the common email, Kenyan phone or labeled patient identifier checks.
- Requests default to `input_classification=sensitive`; hosted use requires an explicit public declaration.
- The identifier checks are deliberately conservative but are not a complete PHI detector and cannot recognize all names or sensitive narratives. They do not make hosted transfer safe for patient data. Do not submit patient information, clinical records, identifiable case narratives or confidential hospital data to the hosted provider.
- The configured data-transfer approval must be backed by an organization's privacy, legal, security and jurisdictional review before enabling the provider.

## Hybrid behavior

When a local provider is enabled, the current policy selects local. When local is not enabled, hybrid mode may select hosted only if `AI_ALLOW_HOSTED=true`. If the selected provider is unavailable, the request fails closed. There is no cross-class fallback.

Offline and degraded modes always require local inference and never select hosted.

## Operational limitations

- No hosted provider, endpoint, key or data-transfer approval is configured by default.
- No PHI detection guarantee, regional residency guarantee or provider contract/legal approval is supplied by this code.
- The generic adapter requires a compatible OpenAI-style `/v1/models` and `/v1/chat/completions` API.
- Usage token/cost accounting is a separate Phase 2 milestone.
- Hosted model outputs remain unvalidated for clinical use and require the same approved-evidence citation checks and clinician review as local outputs.
