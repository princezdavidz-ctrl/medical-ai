# Phase 2 — Central Medical AI engineering closeout

## Outcome

The central AI engineering milestones 2B.1–2B.18 are implemented and merged into `main`. This includes:
- provider-neutral central AI contracts, policy and routing;
- governed medical knowledge, clinical taxonomy and two-person publication workflow;
- evidence-grounded retrieval and citation validation;
- local and hosted provider adapters with strict no-cross-class fallback;
- hybrid/offline/degraded operating-mode controls;
- authorized patient-context adapter and encrypted conversation sessions;
- evaluation/release governance and version-pinned prompt registry;
- durable offline knowledge package and synchronization foundations;
- hospital usage metering and subscription quota enforcement;
- operational dashboard, provider checks, offline queue visibility and emergency pause controls.

Phase 2 is considered complete as an engineering build phase when 2B.19 documentation closeout is merged. It is not a clinical certification or production go-live declaration.

## Current safety posture

- Global AI execution gate remains disabled by default.
- Capability allow-list remains empty by default.
- Clinical-use flag remains false.
- Every response requires clinician review.
- No clinical content has been seeded or approved as a ready-to-use knowledge corpus.
- No model is declared clinically certified.
- No real patient data is approved for development use.
- Hosted inference requires separate data-transfer and legal approval.
- Local runtime deployment, model artifact verification and provider health remain deployment responsibilities.

## External prerequisites before any clinical pilot

1. Deploy PostgreSQL, Redis, API, secret management, TLS, monitoring and backup/recovery infrastructure.
2. Configure and verify a local model runtime and signed/pinned model artifact.
3. Complete hosted provider privacy/data-transfer review if hosted inference is to be used.
4. Provision trusted knowledge publisher keys, reviewer credentials and the privileged governance worker identity.
5. Source, license, clinically review and publish jurisdiction-appropriate medical knowledge and reference data.
6. Provision hospital subscriptions, usage policies and approved model cost rates through trusted billing.
7. Complete privacy impact assessment, threat model, penetration testing and Kenyan legal/regulatory review.
8. Complete independent clinical safety case and per-capability/model/mode evaluations.
9. Execute Phase 5 validation and obtain signed release approvals.
10. Conduct staged deployment and operational sign-off before any patient data or clinical output is used.

## Phase 5 remains separate

See `docs/TEST_REGISTER_PHASE_5.md`. It contains all known backend, migration, security, AI, clinical, interoperability, offline, module, integration and release-readiness tests. No unexecuted item is considered passed.

## Phase 3 handoff

Phase 3 builds the 40 hospital modules as separate domain modules on the shared backend and central AI platform. Each module must have:
- domain-owned database models and migrations;
- API schemas, routes and services;
- role/department scoped permissions;
- hospital tenant isolation and audit events;
- explicit workflows and state transitions;
- integration contracts to the shared central AI capabilities;
- accessibility and operator-facing UI requirements;
- Phase 5 test cases added during development, not run as a blocker.

Implementation remains merge-first: one bounded module milestone per branch/PR, inspect mergeability, merge, verify main, then proceed to the next module.
