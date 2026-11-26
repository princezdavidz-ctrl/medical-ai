# Phase 3.32 — AI Diagnostic Support

## Objective
Provide a structured diagnostic-support workflow that helps authorized clinicians organize clinical problems, review differential possibilities, consider investigations and document their own diagnostic reasoning. It consumes the central Medical AI platform and never autonomously diagnoses or orders tests.

## Functional scope
- Diagnostic support cases bound to an authorized patient and active encounter.
- Structured problem representation, relevant findings, known facts, missing information and red-flag checklist.
- Differential possibilities linked to approved clinical concepts and evidence references.
- Diagnostic test considerations linked to approved laboratory/imaging definitions, with rationale and priority for clinician review.
- Clinician actions to consider, accept, decline or defer suggestions with documented rationale.
- Link to actual laboratory/imaging orders only after a clinician independently creates the order in the source module.
- Diagnostic result review workspace that summarizes existing results without changing source results or reference ranges.
- Longitudinal diagnostic timeline across encounters subject to patient-care assignment and consent.
- Case closure requires clinician-authored assessment and explicit review of outstanding suggestions.
- Feedback and discrepancy reporting for knowledge governance, not automatic production knowledge updates.

## Clinical safety invariants
- Differential items are possibilities, not definitive diagnoses; the clinician owns final diagnosis.
- AI cannot create, modify, sign or cancel laboratory/imaging orders.
- Suggested tests are advisory; ordering remains a separate clinician action in the relevant module.
- Red flags must be surfaced prominently with escalation guidance; no emergency triage delay.
- Existing test results and reference intervals are read-only and retain their original provenance.
- Patient context is fetched server-side and authorization is revalidated at every operation.
- Evidence source, version and review date are retained with every AI-derived suggestion.
- No model confidence score is presented as a calibrated probability unless independently validated.
- The module does not autonomously update the problem list, diagnosis list, prescription or legal medical record.

## Phase 3 / Phase 4 boundary
Phase 3 implements case records, differential/test consideration review and clinician decision capture. Phase 4 connects live laboratory/radiology APIs, result pipelines, terminology services and validated diagnostic evidence providers.

## Verification
Clinical safety, source grounding, patient authorization, no-auto-order, differential integrity, result provenance and escalation scenarios are recorded in docs/TEST_REGISTER_PHASE_5.md. Backend tests remain deferred to Phase 5.
