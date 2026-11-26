# Phase 3.32 — AI Diagnostic Support

## Objective
Provide a clinician-governed diagnostic support workflow that organizes evidence-grounded differential considerations and possible diagnostic tests around one authorized patient, encounter and AI response. It is a structured decision-support module, not a diagnosis engine.

## Functional scope
- Create a diagnostic support case from an exact `clinical_decision_support` assistant message sequence and SHA-256 response digest in an active patient-bound clinical AI session.
- Keep each case bound to one hospital, clinician, patient, encounter, consent and care assignment.
- Add differential suggestions only when the concept code and display name exactly match a currently effective, approved disease concept in the governed medical knowledge base.
- Add laboratory or imaging test considerations only when the code/name match an active definition in the same hospital.
- Bind every differential and test consideration to citation IDs already present in the source assistant response.
- Allow the assigned clinician/session owner to mark differential suggestions considered, ruled out or clinician-confirmed-for-review.
- Allow the clinician to mark test considerations considered or declined.
- Close a case only after every proposed suggestion has a clinician decision and a private vault reference records the closure assessment.
- Keep all diagnostic suggestions separate from the legal diagnosis list and all test considerations separate from actual orders.

## Clinical safety invariants
- AI cannot set a final diagnosis, sign a diagnosis, create a laboratory/imaging order, or change treatment.
- Differential entries are possibilities for clinician consideration, not confirmed conditions.
- Test considerations never create orders. Actual ordering remains in the authorized Laboratory or Radiology module.
- The source assistant message must exist in the bound encrypted session and its digest must match exactly.
- Evidence citation IDs must be a subset of citations attached to that exact assistant response.
- Every create, list, review and close operation revalidates the active session, patient-care assignment and purpose-bound consent.
- Only the session owner may manage the diagnostic case.
- Clinical concept references must be from approved, effective and currently reviewed knowledge documents.
- Test definitions must be active and belong to the same hospital.
- No raw clinical narrative or model-generated diagnosis is stored in the diagnostic support tables; review and closure notes use private vault references.

## Data model
- `diagnostic_support_cases`: patient/session/encounter/consent/assignment binding, source assistant sequence/digest and clinician closure state.
- `diagnostic_differential_suggestions`: governed clinical concept reference, code/name snapshot, source citation IDs and clinician review state.
- `diagnostic_test_considerations`: same-hospital laboratory or imaging definition reference, source citation IDs and clinician review state.

Migration 0055_ai_diagnostic_support creates the three tables with hospital RLS, tenant-aware composite references, source-digest constraints, review-state constraints and indexes.

## API surface
- POST /api/v1/ai/diagnostics/cases
- GET /api/v1/ai/diagnostics/cases/{case_id}
- GET /api/v1/ai/diagnostics/cases/{case_id}/differentials
- POST /api/v1/ai/diagnostics/cases/{case_id}/differentials
- POST /api/v1/ai/diagnostics/cases/{case_id}/differentials/{suggestion_id}/review
- GET /api/v1/ai/diagnostics/cases/{case_id}/tests
- POST /api/v1/ai/diagnostics/cases/{case_id}/tests
- POST /api/v1/ai/diagnostics/cases/{case_id}/tests/{consideration_id}/review
- POST /api/v1/ai/diagnostics/cases/{case_id}/close

## Phase 3 / Phase 4 boundary
Phase 3 provides case binding, governed concept/test references, citation provenance and clinician review. Phase 4 connects these considerations to live diagnostic catalogs and ordering workflows. No orders or final diagnoses are created in Phase 3.

## Verification
All clinical authorization, evidence provenance, concept/test grounding, review, closure, tenant isolation and migration scenarios are registered in `docs/TEST_REGISTER_PHASE_5.md`. Backend tests remain deferred to Phase 5.
