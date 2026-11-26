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
