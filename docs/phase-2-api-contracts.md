# Phase 2 — Central AI API contract

Base prefix: `/api/v1`. All routes require authenticated hospital context unless stated otherwise. Tenant-scoped endpoints use the authenticated `X-Hospital-ID` context and database RLS.

## System readiness

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | PostgreSQL and Redis readiness |

## Central AI

| Method | Path | Purpose |
|---|---|---|
| GET | `/ai/capabilities` | Per-capability gate/provider status, prompt version/digest and tool permissions |
| POST | `/ai/requests` | Evidence-grounded central AI request |
| POST | `/ai/sessions` | Create an encrypted private conversation session |
| GET | `/ai/sessions` | List sessions owned by the authenticated staff user |
| GET | `/ai/sessions/{session_id}` | Read an owned session |
| DELETE | `/ai/sessions/{session_id}` | Delete an owned session |
| GET | `/ai/usage` | Hospital subscription counters and recent usage (hospital admin/director/finance/system admin) |
| GET | `/ai/operations` | Provider, offline knowledge, sync queue and pause status (hospital admin/director/system admin) |
| PUT | `/ai/operations/control` | Pause/resume hospital AI execution (hospital admin/director/system admin) |

### AI request

Request fields:
- `capability`: `medical_information`, `clinical_decision_support`, `lab_interpretation`, `medication_safety` or `radiology_support`.
- `prompt`: bounded text input (1–8,000 characters).
- `input_classification`: `public` or `sensitive`; sensitive input requires an authorized patient-context workflow.
- `patient_context_id`, `encounter_id`: optional identifiers resolved by the authorized patient-context adapter; direct patient identifiers must not be placed in free text.
- `session_id`: optional owned encrypted conversation session.

The response includes content, provider/model identity and version, prompt version and SHA-256 digest, validated evidence citations, `clinical_use_enabled=false`, and `requires_clinician_review=true`.

### Capability and release rules

- AI execution is disabled by default.
- Capability allow-list is empty by default.
- Provider routing is explicit; no local/hosted cross-class fallback.
- Offline and degraded modes must not route to hosted providers.
- Patient-context requests are local-only.
- Only approved/current knowledge is retrieved.
- Prompt/tool/output/workflow contracts are capability-specific and versioned.
- Tool permissions are empty for all current capabilities.
- No API response authorizes diagnosis, prescribing, orders or autonomous treatment.

## Deliberately not exposed yet

- Clinical knowledge ingestion/review/publication endpoints remain restricted to the trusted governance workflow.
- Offline package import and sync repository operations are not exposed as general-purpose hospital APIs.
- Subscription plan and quota provisioning must come from the trusted platform billing workflow; hospitals cannot increase their own limits through the usage API.
- Prompt registry editing and model release activation are not exposed to ordinary hospital users.
- Partner HIE/FHIR exchange APIs are a later interoperability deliverable and require partner onboarding, consent/legal review and conformance work.

This document describes implemented application routes and explicitly identifies service-layer workflows that are not yet public APIs.
