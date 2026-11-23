# Phase 2 — Central Medical AI completion plan

## Goal

Deliver one provider-neutral central medical AI platform for all hospital modules. It must support hosted and locally hosted models, full offline operation for specifically approved tasks, governed medical evidence, hospital isolation, auditable usage and safe fail-closed behavior.

Phase 2 is complete only when the central platform's engineering components are implemented and documented. Clinical certification, production deployment and patient-care activation remain separate approval gates and Phase 5 validation activities.

## Already merged

- Phase 2A: hybrid hosted/local architecture with full offline requirement.
- 2B.1–2B.8: AI contracts, policy engine, model gateway, approved medical knowledge retrieval, evidence citations, local model adapter and authenticated request wiring.
- 2B.9: evaluation and clinical release gate contracts.
- 2B.10: durable evaluation, threshold, release and approval registry schema.

## Remaining development milestones

1. [IMPLEMENTED] **2B.11 — Signed offline knowledge packages.** Verify Ed25519 publisher signatures, SHA-256 payload integrity, schema compatibility, jurisdiction and freshness before a package can enter the offline import pipeline.
2. [IMPLEMENTED] **2B.12 — Durable offline synchronization.** Persist package installation state, monotonic event cursors, idempotency keys, conflict records, retry queues and explicit acknowledgements. Never mark remote delivery complete without partner acknowledgement.
3. [IMPLEMENTED] **2B.13 — Authorized patient-context adapter.** Add purpose-bound patient lookup, consent/lawful-basis checks, hospital membership and assignment checks, minimum-necessary context assembly, access audit and emergency-access review. No patient context may be sent to a hosted provider.
4. **2B.14 — Hosted model provider.** Add an explicit hosted provider implementation, secret-backed credentials, approved endpoint/model allow-list, request minimization, region/data-transfer policy, timeout/cost limits and no cross-class fallback. It remains disabled until configured and approved.
5. **2B.15 — AI conversation sessions.** Add hospital-scoped sessions, message persistence, retention controls, safe context reconstruction, user ownership checks, deletion/export and privacy-preserving audit events.
6. **2B.16 — AI usage and subscription enforcement.** Meter tokens, requests, model/provider, capability, mode, latency and estimated cost by hospital/tenant; enforce quotas and subscription limits without exposing another tenant's usage.
7. **2B.17 — Capability prompt and workflow registry.** Version system prompts, tool permissions, output schemas and clinical workflow contracts independently for each capability; pin all versions to evaluation runs.
8. **2B.18 — Central AI operational controls.** Add health/readiness, provider availability, offline package freshness, queue status, usage dashboards and administrator controls with strict RBAC and audit.
9. **2B.19 — Phase 2 integration and documentation closeout.** Wire the components together, publish API contracts and operator runbooks, record remaining external deployment prerequisites, and verify all Phase 2 deliverables are represented in the Phase 5 Test Register.

## Non-negotiable architecture rules

- One central AI platform serves the 40 hospital modules; modules call approved capabilities rather than creating independent AI brains.
- Hybrid means explicit hosted/local routing. Offline and degraded modes must never call hosted providers.
- Patient-context requests are local-only unless a separately approved lawful architecture explicitly changes this policy.
- No automatic provider-class fallback.
- Only approved, current, jurisdiction-appropriate knowledge may be retrieved.
- Every clinical response must preserve provenance, citations, uncertainty and clinician-review requirements.
- Capabilities remain disabled by default. Successful engineering milestones do not authorize clinical use.
- Evaluation and clinical approvals are tied to exact model, prompt, policy, dataset, evaluator and knowledge snapshot versions.
- Tenant isolation, consent, purpose limitation and audit requirements apply to every AI path.
- Full offline support is implemented per approved capability; it does not mean every task is permitted offline.

## Phase 2 completion exit criteria

- All 2B.11–2B.19 milestones merged into main.
- Provider-neutral routing supports local and hosted providers with strict operating-mode rules.
- Approved medical evidence retrieval and offline knowledge distribution are integrated.
- Patient-context access is permissioned, consent-aware, minimal and auditable.
- Sessions, usage metering and tenant quota enforcement are implemented.
- Evaluation/release governance is durable and integrated with deployment controls.
- All API and operational contracts are documented.
- All known verification work is recorded in the Phase 5 Test Register.
- Clinical use remains disabled until independent clinical, legal, security and regulatory approval and Phase 5 evidence are complete.

After these exit criteria are met, begin Phase 3: build the 40 hospital modules in the agreed module order and connect them to the central AI capability API.
