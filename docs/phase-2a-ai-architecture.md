# Phase 2A — Central Medical AI Architecture Plan

**Status:** Planning baseline — no clinical AI implementation is authorized by this document alone.  
**Project:** Medical AI Hospital System  
**Architecture principle:** One central, governed AI platform serving all hospital modules through controlled, department-aware capabilities.

## 1. Objectives and non-goals

### Objectives
1. Provide one central AI gateway and shared reasoning/orchestration layer for all 40 hospital modules.
2. Ground medical answers in a curated, versioned, searchable medical knowledge base with source provenance.
3. Retrieve patient-specific information only through authorized hospital APIs and only within the requesting user's permitted scope.
4. Support clinical decision support, diagnostics assistance, laboratory interpretation support, radiology assistance, medication safety, patient communication, analytics and workflow assistance.
5. Keep the model provider-independent, with configurable hosted-model and local/offline fallback adapters.
6. Require clinician or authorized staff approval for consequential clinical decisions and workflow actions.
7. Make AI activity auditable, measurable, tenant-isolated and continuously evaluable.

### Non-goals
- The AI is not an autonomous doctor, prescriber, pharmacist, radiologist, nurse or emergency dispatcher.
- It must not independently diagnose, prescribe, discontinue medication, authorize procedures, disclose records, accept transfers or execute high-impact clinical actions.
- It must not train on identifiable patient records by default.
- It must not treat model confidence as clinical certainty or claim complete medical knowledge.

## 2. High-level architecture

The central AI is a logical platform, not 40 independent AI products. Department assistants are bounded capabilities routed through the same gateway, policy checks, knowledge services, audit layer and evaluation framework.

```text
Hospital web/mobile portals and 40 modules
                  |
          Authenticated API
                  |
       Central Medical AI Gateway
                  |
     Identity / Tenant / Permission Context
                  |
       AI Policy & Safety Orchestrator
                  |
       Request Classification / Router
        /          |          \
 Clinical CDS   Knowledge    Operational
 & agents       Retrieval    assistants
        \          |          /
          Context Assembly
                  |
       Model Abstraction Gateway
        /                       \
 Hosted model providers     Local/offline model
        \                       /
           Structured AI result
                  |
      Evidence / uncertainty / warnings
                  |
       Human review and approval
                  |
     Existing authorized module APIs
                  |
      Audit, monitoring and evaluation
```

### Logical services
| Service | Responsibility |
|---|---|
| AI Gateway | Authenticates requests, applies rate limits, assigns request IDs and exposes stable APIs |
| Context & Policy Service | Enforces tenant, user, role, department, patient relationship, consent and purpose-of-use rules |
| Orchestrator | Classifies task, selects approved capability, coordinates retrieval and model calls |
| Medical Knowledge Service | Searches approved medical sources and returns evidence with provenance |
| Patient Context Adapter | Retrieves minimum necessary patient context from existing hospital APIs |
| Model Gateway | Selects approved hosted/local model, handles timeouts, fallback and model versioning |
| Safety Layer | Applies task-specific rules, red-flag checks, output validation and escalation |
| Human Review Service | Presents recommendations for review, approval, rejection or amendment |
| Audit & Observability | Records access, source IDs, model/version, policy decisions, approvals, latency and cost |
| Evaluation Service | Runs regression, safety, quality, bias and drift evaluations before release |

These are logical boundaries. Begin as modules within the existing backend/deployment where practical; extract separate services only when scale, security isolation or operational needs justify it.

## 3. Department capability map

All capabilities use the same shared platform. They differ by approved tools, prompts, data permissions, output schema and human approval rules.

| Capability | Initial responsibilities | Required boundary |
|---|---|---|
| General Medical Assistant | Explain conditions, summarize evidence, support clinician questions | Cite sources; distinguish facts from possibilities |
| Diagnostic Support | Generate differential considerations and suggest relevant investigations | Never finalize a diagnosis or independently order tests |
| Laboratory Assistant | Explain test methods, units, reference intervals, trends and critical values | Use the reporting laboratory's range and verified result context |
| Radiology Assistant | Help organize imaging findings and draft structured report support | Radiologist retains interpretation and sign-off |
| Pharmacy Assistant | Check medication context, interactions, contraindications and dose references | Pharmacist/prescriber retains prescribing and dispensing authority |
| Nursing Assistant | Summarize care plans, observations and nursing guidance | Nurse retains assessment and administration decisions |
| Emergency Support | Surface red flags, protocols and escalation prompts | Never delay emergency care or autonomously triage/discharge |
| Patient Assistant | Explain approved instructions, appointments and care information | No independent diagnosis or treatment changes |
| Hospital Operations Assistant | Summarize staffing, inventory, workflow and operational metrics | Access only authorized operational data |
| Voice Assistant | Speech input/output for approved capabilities | Confirm identity, intent and critical values; no voice-only authorization |

Additional departmental capabilities are added through configuration and governed APIs, not by creating isolated models for each module.

## 4. Medical knowledge base

### Knowledge domains
- Diseases and conditions, including rare conditions where reliable evidence is available.
- Symptoms, signs, risk factors, complications and differential diagnoses.
- Diagnostic tests, procedures, preparation, methods, limitations and interpretation.
- Laboratory reference intervals, units, abnormal flags and critical-result escalation.
- Clinical guidelines, treatment pathways and referral criteria.
- Medicines, indications, contraindications, interactions, adverse effects and dosing references.
- Pregnancy, pediatrics, older adults, renal/hepatic impairment and other context-specific cautions.
- Infection prevention, emergency protocols and patient education.

### Source governance
Every source and knowledge item must carry:
- Source title, publisher/authority, canonical reference and licensing/usage status.
- Jurisdiction and care setting.
- Publication/effective date, review date and version.
- Evidence type/grade where the source supports it.
- Clinical reviewer, approval status and change history.
- Applicable patient population and known limitations.
- Superseded/withdrawn status and scheduled re-review date.

Only approved, appropriately licensed sources enter the production knowledge index. A source ingestion pipeline must quarantine unreviewed content. Conflicting guidance must be surfaced with source dates and jurisdiction rather than silently blended.

### Retrieval design
- Store source metadata, document versions and review state in PostgreSQL.
- Store searchable chunks with embeddings using pgvector initially.
- Use hybrid retrieval: lexical search plus vector similarity, metadata filters and reranking.
- Filter by approved status, jurisdiction, date, population and task.
- Return evidence snippets and source identifiers to the model; the final response must cite the retrieved sources.
- Preserve exact units and laboratory-specific reference intervals. Never substitute a generic range when the patient's laboratory range is available.
- Keep medical knowledge separate from patient records and from operational analytics.

### Separate data planes
1. **General medical knowledge:** approved reusable evidence and guidance.
2. **Patient context:** patient-specific records fetched on demand from authorized clinical APIs.
3. **Operational knowledge:** hospital policies, workflows and non-clinical operating procedures, each with its own access controls.

These indexes must not be silently combined. Patient data is not a general knowledge corpus and is not used for model training without separately approved lawful basis, governance and safeguards.

## 5. Patient context and authorization

Before any patient-context retrieval, the platform must establish:
- Authenticated staff identity and active hospital membership.
- Hospital tenant and department scope.
- Role and fine-grained permissions.
- Whether the user is assigned to, participating in or otherwise authorized to access the patient.
- Purpose of use and relevant consent/lawful basis.
- Minimum information required for the specific task.

The AI must never use a patient identifier supplied in a prompt as proof of authorization. It must call existing authorized APIs, which independently enforce access. Cross-hospital information is available only through the approved request-based HIE workflow; no implicit partner-hospital access.

Emergency/break-glass access, where legally permitted, is a separately governed workflow with reason capture, restricted scope, immediate audit and retrospective review. AI cannot grant itself emergency access.

## 6. Model strategy and offline resilience

### Model abstraction
Create a provider-neutral interface so that application modules do not depend directly on one model vendor. Each model configuration records:
- Provider and model identifier/version.
- Approved tasks and data classification.
- Region/hosting mode and contractual privacy posture.
- Context window, structured-output support and tool-calling capability.
- Cost limits, timeout, retry and fallback policy.
- Evaluation results and approval status.

### Hosted and local/offline modes
- Hosted models may be used only after security, privacy, contractual and task-specific evaluation.
- A local/offline model is an availability fallback for explicitly approved tasks.
- Offline mode must clearly identify reduced capability and unavailable services.
- If the local model cannot meet the task's safety/quality threshold, return a safe unavailable/escalation response; do not fabricate an answer.
- High-risk clinical tasks may be disabled in offline mode unless that exact model/task combination has passed its own clinical evaluation.
- No automatic failover may send restricted patient data to an unapproved provider.

## 7. Standard request and response contract

Every AI request should include a server-generated request ID, authenticated actor, hospital context, task type, purpose, optional patient reference, data classification, locale and requested output schema. The client must not be able to override trusted authorization context.

Every response should provide, where applicable:
- A concise answer or structured recommendation.
- Task classification and model/version metadata.
- Evidence/source references and source dates.
- Missing information and assumptions.
- Uncertainty/limitations and confidence language that is not presented as a probability unless calibrated.
- Red flags, contraindications and escalation instructions.
- Whether human review is required.
- A structured action proposal, never an executed action, for workflows requiring approval.

Clinical response schemas must be task-specific. A diagnostic-support response, lab interpretation and medication-safety check must not share one vague free-text contract.

## 8. Human approval and action controls

The AI may prepare drafts, summaries, suggestions and proposed actions. It cannot directly commit high-impact changes.

Approval gates are required before:
- Signing or finalizing a diagnosis, clinical note or radiology report.
- Creating, changing or discontinuing a prescription.
- Ordering a test or procedure.
- Recording medication administration.
- Discharging, transferring or changing a patient's level of care.
- Sending sensitive clinical communication externally.
- Disclosing records to another facility.
- Executing consequential hospital workflow or financial actions.

The approval record must identify the human reviewer, their role, decision, timestamp, changes made and the exact AI recommendation/version reviewed. Rejection and amendment are first-class outcomes. The AI must not approve its own proposal.

## 9. Safety, privacy and security controls

- Tenant isolation enforced by backend authorization and PostgreSQL RLS; never rely on prompt instructions for security.
- Least-privilege service identities and separate credentials for each integration.
- Encryption in transit and at rest, managed secrets, rotation and key access auditing.
- Redaction/minimization of prompts, logs and telemetry; never log passwords, tokens or unnecessary clinical text.
- Prompt-injection defense: retrieved documents and user-provided files are untrusted data, not system instructions.
- Tool allowlists, schema validation, bounded calls, timeouts and explicit human confirmation for consequential actions.
- Output validation for required fields, units, ranges, prohibited actions and missing evidence.
- Rate limits, abuse monitoring, incident response and retention controls.
- Model/provider data-use restrictions and contractual review before protected data is sent externally.
- Versioned prompts, policies, retrieval configuration and models so each decision can be reconstructed.
- Clinical governance and applicable privacy, health-record, medical-device and professional requirements reviewed for each deployment jurisdiction.

## 10. Proposed AI data model

Initial logical entities; final table design follows the backend's migration conventions.

| Entity | Purpose |
|---|---|
| ai_agents | Approved capability definitions and scope |
| ai_model_providers | Provider configuration references; no plaintext secrets |
| ai_model_versions | Model identity, approval, evaluation and supported tasks |
| ai_prompts | Versioned system/task prompt templates |
| ai_policies | Versioned safety, privacy and action policies |
| ai_sessions | User- and tenant-scoped conversation sessions |
| ai_messages | Redacted/controlled message records and structured outputs |
| ai_requests | Request lifecycle, task, actor, purpose and correlation ID |
| ai_knowledge_sources | Publisher, license, jurisdiction, version and review state |
| ai_knowledge_documents | Source document versions and ingestion status |
| ai_knowledge_chunks | Searchable text chunks, metadata and embeddings |
| ai_retrieval_events | Retrieved source IDs, ranks and filters |
| ai_patient_context_events | Auditable references to patient data accessed; avoid duplicating records |
| ai_recommendations | Structured proposed recommendations/actions |
| ai_approvals | Human review, approval, rejection and amendment |
| ai_safety_events | Warnings, blocked actions, escalations and incidents |
| ai_evaluations | Dataset/version, test result and release decision |
| ai_feedback | Clinician feedback with review status |
| ai_usage_logs | Token/compute use, latency and cost by tenant/capability |
| ai_audit_events | Security-relevant immutable/tamper-evident event references |

All tenant-owned entities require hospital scoping and RLS. Global reusable knowledge must have explicit publication governance and must not accidentally inherit one hospital's patient context. Secrets are stored in a secrets manager; database rows contain references only.

## 11. API surface proposal

Versioned internal APIs, subject to detailed contract design:
- `POST /api/v1/ai/requests` — submit an authorized AI task.
- `GET /api/v1/ai/requests/{request_id}` — retrieve request status/result.
- `POST /api/v1/ai/sessions` and `GET /api/v1/ai/sessions/{session_id}` — manage scoped sessions.
- `POST /api/v1/ai/recommendations/{id}/review` — approve, reject or amend a proposal.
- `GET /api/v1/ai/agents` — list capabilities available to the authenticated actor.
- `POST /api/v1/ai/knowledge/sources` — submit a source for controlled ingestion (restricted governance role).
- `POST /api/v1/ai/knowledge/sources/{id}/review` — approve, reject or supersede a source (clinical governance role).
- `GET /api/v1/ai/usage` — authorized tenant usage and cost reporting.
- `GET /api/v1/ai/audit` — authorized AI activity audit access.

These are proposed platform APIs, not existing implemented endpoints. Module-specific APIs remain authoritative for committing clinical or operational changes.

## 12. Evaluation and release gates

Before enabling any capability with clinical impact:
1. Define intended use, excluded use, user population and accountable clinical owner.
2. Build a versioned, de-identified or synthetic evaluation set reviewed by qualified clinicians.
3. Evaluate factuality, source support, omissions, uncertainty, critical red-flag sensitivity, false alarms, subgroup performance and harmful recommendations.
4. Test retrieval coverage, stale/conflicting sources, wrong units, missing context and prompt injection.
5. Test tenant isolation, role/department boundaries, consent restrictions and audit completeness.
6. Compare hosted and local models separately; do not assume equivalent quality.
7. Establish task-specific acceptance thresholds and a documented release decision.
8. Monitor post-release performance, feedback, incidents, source updates and model drift; support rollback.

No single overall accuracy score is sufficient for clinical release. Safety-critical failure modes require their own thresholds and review.

## 13. Delivery sequence for Phase 2

The detailed implementation backlog should be approved after this architecture plan. Proposed order:
1. AI platform contracts, threat model, data classification and clinical governance.
2. AI gateway, tenant-aware authorization and audit foundation.
3. Knowledge-source registry, ingestion, clinical review and versioning.
4. Search, embeddings, hybrid retrieval and evidence citations.
5. Model gateway with approved hosted/local adapters and fail-safe behavior.
6. Shared orchestration and first low-risk capability.
7. Human approval workflow and integration with one selected module.
8. Evaluation harness, monitoring, usage/cost controls and controlled expansion to remaining capabilities.

## 14. Decisions to lock in during Phase 2A

The architecture review must explicitly settle:
- Initial hosted model/provider and local/offline model candidates.
- Whether embeddings and reranking run locally or through an approved provider.
- Initial medical knowledge sources, licenses, jurisdiction and clinical reviewers.
- Patient-context fields permitted for each first capability.
- Which first capability is piloted and its accountable clinical owner.
- Retention policy for prompts, responses, source excerpts and audit metadata.
- Approval roles and exact actions that remain human-controlled.
- Clinical evaluation thresholds and release authority.

## 15. Phase 2A completion criteria

Phase 2A is complete only when:
- The central AI architecture and trust boundaries are approved.
- The knowledge governance and source licensing process is defined.
- Tenant-aware patient-context access and authorization are specified.
- Hosted/local model strategy and safe fallback behavior are agreed.
- The capability map and human approval matrix are approved.
- AI data model and API contracts are reviewed.
- Clinical safety, privacy, security and evaluation plans have named owners.
- The implementation backlog is prioritized and accepted.

**Important:** This plan is an architecture proposal. It does not authorize production use, external model transmission of patient data, autonomous clinical decisions or deployment of unvalidated AI capabilities.


## 16. Locked decision: hybrid AI with full offline capability

**Decision status:** Approved by the project owner for the Phase 2A architecture baseline.  
**Selected strategy:** Hybrid — approved hosted models plus hospital-controlled local models.  
**Offline requirement:** Full offline capability for the hospital platform's explicitly supported functions, with task-specific AI availability determined by local evaluation and hardware capacity.

This decision means the project owns the complete Medical AI platform and its control plane: gateway, orchestration, policies, knowledge governance, retrieval, safety checks, capability definitions, audit, evaluation and user experience. Hosted and local models are interchangeable reasoning engines behind our own model gateway. The system is not a thin wrapper around one vendor API.

### 16.1 Operating modes

| Mode | Behavior |
|---|---|
| Connected / hybrid | Use approved hosted or local models according to task policy, data classification, quality, latency, cost and availability. |
| Offline | Keep the hospital application and approved local AI capabilities operating without internet or hosted model access. |
| Degraded / isolated | If a local model, local knowledge index or required dependency is unavailable or fails its evaluation threshold, disable only the affected capability, explain the limitation and provide the approved human/manual workflow. |

The model router must not silently change the task's safety level when switching modes. It must record which model, model version, mode, policy and knowledge snapshot served each request.

### 16.2 Full offline requirement — scope and boundaries

"Full offline" is a system resilience requirement, not a promise that every advanced AI capability will work without connectivity. The design must support:

- Hospital login and locally available identity/authorization checks, subject to the approved offline session and revocation policy.
- Access to the hospital's locally available patient records and operational data under the same role, department, tenant and purpose-of-use controls.
- Locally hosted AI models for capabilities that have passed independent offline clinical and technical evaluation.
- Local medical knowledge search, hybrid retrieval and citations from a versioned, approved knowledge snapshot.
- Local language/voice processing only where the required speech models and language packs are installed and evaluated.
- Local audit/event queuing with durable storage, timestamps and tamper-evident sequencing; queued events synchronize when connectivity returns.
- Offline-safe workflows and clear status indicators for unavailable external integrations, hosted models, partner hospitals, national services and live data sources.
- Controlled synchronization with idempotency, conflict handling, replay protection and delivery acknowledgements.

Offline operation must not create an authorization bypass. Cached patient information must remain encrypted, scoped, access-controlled and subject to retention/expiry rules. Revocation and account disablement must be reconciled safely; the offline policy must define maximum cache age and the response when authorization freshness cannot be established.

### 16.3 Local-first data and model architecture

- Run the local model runtime within hospital-controlled infrastructure or an approved private deployment. Keep model serving behind the same authenticated Model Gateway contract used for hosted providers.
- Keep the approved medical knowledge index, embeddings, retrieval/reranking components and necessary reference metadata available locally.
- Maintain explicit model/task approval records, hardware requirements, resource limits, version pinning, checksums and rollback packages.
- Support a local-only processing policy for data classes that are not approved for external processing.
- Hosted provider access is opt-in per approved task and data class; no restricted patient data may be sent to a hosted provider merely because the local model is busy or unavailable.
- Downloads, updates and knowledge synchronization happen through signed, verified packages when connectivity is available. Offline sites must be able to continue using the last approved snapshot and show its version/date.
- The local runtime must have resource isolation, health checks, bounded queues, concurrency limits and graceful degradation so AI cannot starve core hospital services.

### 16.4 Safety rules across modes

- Every capability is evaluated separately on hosted and local model configurations. Passing one does not approve the other.
- High-risk diagnostic, medication, emergency, radiology and other clinical tasks remain disabled or restricted offline until that exact local model, retrieval snapshot and workflow pass the relevant clinical release gates.
- The system must not invent a result when the model, evidence, patient context or required service is unavailable.
- Critical alerts, emergency escalation and clinical action approvals must follow hospital-approved procedures; AI is not the sole emergency channel.
- Human approval remains mandatory for consequential clinical actions in both connected and offline modes.
- Patient data is not used to train or fine-tune models by default. Feedback is collected as governed evaluation material only after appropriate review and lawful approval.

### 16.5 Connectivity and synchronization controls

Introduce an explicit connectivity/operating-mode service with:
- Health status for internet, hosted providers, local model runtime, local knowledge index, hospital database and synchronization queue.
- Per-capability availability, rather than one misleading global "AI online" flag.
- Durable outbound event queue, idempotency keys, retry/backoff, dead-letter handling and operator-visible reconciliation.
- Conflict rules for records changed both locally and remotely; clinical record conflicts require authorized human resolution.
- Signed/versioned knowledge and model package manifests, integrity verification and rollback.
- Monitoring for queue age, storage pressure, failed synchronization, stale knowledge and local model resource exhaustion.

A successful local write must be distinguished from a successfully synchronized remote write. The user interface must never display a remote delivery or partner-hospital acknowledgement until it has actually been received.

### 16.6 Additional architecture components

Add these logical components to the existing architecture (initially modular within the backend where practical):

| Component | Responsibility |
|---|---|
| Local Model Runtime Manager | Deploys, monitors, versions and health-checks hospital-controlled model runtimes |
| Offline Knowledge Node | Serves approved local medical knowledge, embeddings and retrieval indexes |
| Connectivity & Mode Manager | Determines connected/offline/degraded state and per-capability availability |
| Sync & Reconciliation Engine | Queues, verifies, retries and reconciles authorized data/events after reconnection |
| Model/Knowledge Package Manager | Verifies signed releases, manifests, checksums, compatibility and rollback |
| Offline Audit Buffer | Durably records access, AI decisions and actions until secure synchronization is possible |

### 16.7 Additional data model requirements

Extend the proposed model with these entities or equivalent tables after detailed schema review:

- ai_runtime_deployments — site, runtime, hardware profile, status and deployed version.
- ai_capability_model_approvals — exact capability/model/version/mode approval and evaluation reference.
- ai_knowledge_release_snapshots — approved knowledge release, jurisdiction, version, checksum and effective dates.
- ai_site_sync_cursors — synchronization position and last acknowledged event per site/stream.
- ai_sync_events — durable event metadata, idempotency key, delivery attempts and acknowledgement state.
- ai_connectivity_events — mode transitions and dependency health history.
- ai_package_manifests — signed model/knowledge package metadata and integrity verification state.

These records must not store plaintext secrets. Tenant-owned records remain hospital-scoped and protected by authorization/RLS. Global package metadata must be separated from hospital-specific deployment state.

### 16.8 Revised implementation backlog

The Phase 2 implementation backlog must now include:

1. **Architecture and governance:** document site deployment topology, offline threat model, data classification, cache/retention rules, offline identity/revocation policy and clinical owners.
2. **Model Gateway:** define provider-neutral hosted/local adapters, task routing, data-class policy, timeouts, quotas, version pinning and fail-closed fallback.
3. **Local AI runtime:** select candidate open-weight models and runtime only after hardware, license, language, privacy and task requirements are documented.
4. **Local knowledge:** build governed ingestion and review, local snapshots, lexical/vector retrieval, citations, version checks and rollback.
5. **Offline application resilience:** define which hospital functions work without connectivity, local dependency behavior, operator indicators and safe degraded workflows.
6. **Synchronization:** implement durable queues, idempotency, signatures/integrity, retries, conflict resolution, acknowledgements and reconciliation.
7. **Evaluation:** establish separate hosted/local task-specific test suites, including offline retrieval, stale-source behavior, latency, resource pressure, adversarial inputs and clinical safety.
8. **Pilot:** deploy to a controlled non-production hospital-like environment using synthetic/de-identified data before any clinical use.
9. **Release governance:** require clinical, privacy, security and operations sign-off for each capability and each operating mode.

### 16.9 Phase 2A decision record

The following decisions are now locked:
- One central Medical AI platform shared by all 40 modules.
- Hybrid hosted + hospital-controlled local model strategy.
- Full offline system capability as a design requirement, with per-capability safety qualification.
- Own provider-neutral Model Gateway; no direct vendor coupling in modules.
- Local approved medical knowledge and retrieval capability.
- No automatic external transmission of restricted patient data.
- No autonomous clinical decisions; human approval gates remain in force.
- No default training on identifiable patient records.
- Offline synchronization must be explicit, durable, auditable and conflict-aware.

The following remain open design choices for the implementation backlog, not reasons to delay the architecture decision: initial model candidates, local runtime technology, deployment hardware profile, initial hosted provider, embedding/reranking implementation, knowledge source licenses, first pilot capability, cache retention limits and task-specific clinical thresholds.

## 17. Updated Phase 2A completion criteria

In addition to the original completion criteria, Phase 2A must produce:
- A connected/offline/degraded operating-mode specification and capability availability matrix.
- A local deployment and hardware-sizing decision record based on actual site requirements.
- A model/provider policy covering hosted/local routing, data classification and fail-closed behavior.
- A local knowledge snapshot, update, integrity and rollback design.
- An offline identity, authorization freshness, cache and revocation policy.
- A synchronization and conflict-reconciliation contract.
- Separate hosted and local evaluation/release gates.
- A prioritized implementation backlog with clinical, privacy, security and operations owners.

**Safety and deployment note:** Full offline capability does not mean that all 40 AI capabilities are automatically approved for offline clinical use. Each task, model version, knowledge snapshot and workflow must pass its own release gates. Until those approvals are complete, the platform is an engineering/planning system and must not be used to make or execute clinical decisions.
