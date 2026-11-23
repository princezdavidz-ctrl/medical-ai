# Phase 2B — Central Medical AI Core Foundation

## Objective
Implement one provider-neutral Medical AI control plane shared by the hospital modules. This milestone establishes safe contracts and fail-closed behavior; it does not enable clinical AI output.

## Implemented foundation
- Typed capability and operating-mode contracts.
- Explicit capability approval policy; all capabilities are disabled by default.
- Provider-neutral model gateway with local/hosted provider classes and no cross-class fallback.
- Orchestrator contract that requires approved retrieved evidence before model execution.
- Authenticated, hospital-scoped capability discovery and request endpoint.
- Minimal audit event for blocked requests; prompts and patient identifiers are excluded from audit metadata.
- Patient-context requests are blocked until a tenant-authorized patient context adapter exists.

## Current runtime status
No hosted provider, local model runtime, medical knowledge retriever, or patient-context adapter is registered by this milestone. Requests therefore fail closed and return an explicit unavailable response. The API must not fabricate clinical answers or claim that offline inference is ready.

## Safety invariants
1. Every request requires the existing hospital-scoped bearer authentication.
2. Capability approvals are explicit and default to disabled.
3. Offline/degraded modes require a local model; they never route to hosted providers.
4. Patient-context requests cannot route to hosted models.
5. Retrieved approved evidence is mandatory before model invocation.
6. No prompt text or patient identifier is written to the audit event metadata.
7. This foundation is not approved for clinical use.

## Next milestones
- Add versioned AI request/session/recommendation persistence and tenant RLS.
- Implement governed medical knowledge ingestion, review, local snapshots and hybrid retrieval.
- Add the local model runtime and evaluate candidate open-weight models on approved tasks.
- Add hosted model adapters only after provider, data processing and jurisdiction approvals.
- Implement patient-context authorization adapter, consent/purpose checks and audit detail.
- Add separate hosted/local evaluations, release gates and offline synchronization.
