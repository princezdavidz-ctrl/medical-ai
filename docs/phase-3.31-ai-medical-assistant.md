# Phase 3.31 — AI Medical Assistant

## Objective
Deliver a role-aware clinical decision-support workspace that connects hospital users to the central Medical AI platform completed in Phase 2. This module presents structured clinical reasoning support while preserving clinician accountability and source traceability.

## Functional scope
- Clinician-facing assistant workspace embedded in department-specific dashboards.
- Context selection for patient, encounter, age band, relevant history, allergies, medications and available observations, subject to existing patient-care authorization.
- Structured response sections: problem representation, possible differential diagnoses, red flags, suggested diagnostic considerations, medication safety considerations, monitoring and escalation prompts.
- Evidence and medical knowledge references with source/version metadata and review date.
- Clinical note drafting support with explicit clinician review and signature before saving to the medical record.
- Conversation/session history with access controls, audit events and retention policy integration.
- Feedback and correction workflow for clinicians; governed evaluation signals do not directly change production knowledge or model behavior.
- Offline/local inference status and synchronization indicators consistent with the Phase 2 hybrid architecture.
- Safe degraded-mode behavior when the AI runtime or medical knowledge store is unavailable.

## Clinical safety invariants
- Clinical decision support only; never autonomous diagnosis, prescribing, ordering, triage disposition or discharge.
- AI output is advisory and must be reviewed by an authorized clinician before clinical use.
- Patient context is fetched server-side after checking hospital membership, care-team assignment, encounter scope and consent where required.
- The client cannot submit arbitrary patient facts as trusted chart data; user-supplied context is labeled as such.
- No medication recommendation is presented without allergy, interaction, contraindication and dose-context checks where the knowledge base supports them.
- Emergency red flags trigger clear escalation language and do not delay emergency care.
- Responses distinguish known chart facts, user-provided statements, model inference and missing information.
- Every response records model release, knowledge snapshot, prompt/workflow version, user, hospital, patient/encounter references and safety flags.
- No AI output is written into the legal medical record without clinician approval and attribution.

## Phase 3 / Phase 4 boundary
Phase 3 builds the assistant session, context authorization, structured response contract, clinician review workflow and audit trail. Phase 4 connects the assistant to every clinical module API, production knowledge index, model-serving infrastructure, offline synchronization and external clinical reference services.

## Verification
Clinical safety, authorization, prompt injection, source grounding, medication safety, offline behavior, audit, latency and failure-mode scenarios are registered in docs/TEST_REGISTER_PHASE_5.md. Backend tests remain deferred to Phase 5.


## Implemented foundation
- Patient-bound clinician AI sessions require active clinical role, patient-care assignment, in-progress encounter and purpose-bound consent before session creation.
- A clinical session is permanently bound to one hospital, owner, patient, encounter, consent and care assignment; the same session cannot be switched to another patient.
- Every clinical AI request revalidates the current patient assignment and consent. If the original consent or assignment changes, the session must be restarted.
- Clinical decision support prompt v2 enforces explicit sections for problem representation, differential considerations, red flags/escalation, diagnostic considerations, medication safety, missing information and evidence/limitations.
- Assistant responses expose a SHA-256 digest and assistant message sequence. The encrypted session stores the digest as metadata without storing plaintext outside encrypted messages.
- Clinicians can record accepted-for-consideration, rejected or needs-revision decisions against the exact assistant response digest. Review records are append-only and may include a private vault reference to a separately saved clinical note.
- The workflow does not write AI output into the legal medical record or autonomously order, diagnose, prescribe, triage or discharge.
- Migration 0053_ai_clinical_assistant creates patient-bound session context and immutable clinician review records with RLS.

## API additions
- POST /api/v1/ai/clinical-sessions
- POST /api/v1/ai/clinical-sessions/{session_id}/reviews
- GET /api/v1/ai/clinical-sessions/{session_id}/reviews
- POST /api/v1/ai/clinical-sessions/{session_id}/revoke
- Existing POST /api/v1/ai/requests accepts the created session ID plus the same patient and encounter references; it returns session ID, assistant sequence and response digest.


## Clinician feedback and correction workflow
- Each response review records a structured feedback category (`helpful`, `inaccurate`, `missing_context`, `unsafe`, `unsupported`, `needs_revision` or `other`) alongside the existing accept/reject/revise decision.
- Detailed correction material and separately saved clinical note drafts are referenced only by private `vault://` identifiers; plaintext feedback narratives are not added to the review ledger.
- The session owner can retrieve their review history only while the patient-bound session remains active and the original consent and care assignment still authorize access.
- Feedback records are append-only and are governance/evaluation signals only. They do not modify production prompts, medical knowledge or model weights.
- Migration 0054_ai_clinical_feedback adds the structured category and private correction reference to the immutable review ledger.

## Additional API
- GET /api/v1/ai/clinical-sessions/{session_id}/reviews


## Session revocation
The session owner can explicitly revoke a patient-bound clinical AI session. Revocation is recorded with a controlled reason code and timestamp; subsequent AI requests and review-history reads fail because they require an active clinical session. Revocation does not delete encrypted history or bypass the configured retention policy.
