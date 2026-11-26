# Phase 3.35 — AI Pharmacy Assistant

## Objective
Provide pharmacists and authorized clinicians with a governed, read-only medication safety review workflow using verified medication orders and approved medical knowledge. The assistant is clinical decision support only.

## Source eligibility and binding
- Cases are created only for active, verified medication orders belonging to the same patient and encounter in the same hospital.
- Each case binds to an active patient-bound clinical AI session and exact assistant response sequence/digest under the `MEDICATION_SAFETY` capability.
- Medication definition, ingredient, strength, formulation, dose, route, frequency, duration and order state are captured in an immutable snapshot.
- Consent, purpose and care assignment are revalidated on create, read and review.

## Evidence and patient context
- Only active, approved and current medication-safety rules and evidence sources may be presented as supporting evidence.
- Preserve citation IDs, source/document identifiers, publisher, version, evidence grade and review dates.
- Do not infer allergy status, pregnancy, renal/hepatic function, body weight, age-specific dosing suitability or adherence when those facts are absent.
- Missing or conflicting patient context is surfaced as unknown; the assistant must not invent a safe dose or treatment decision.

## Clinical and operational boundaries
- Read-only review only: no prescribing, dose changes, discontinuation, order approval, dispensing, medication administration or claims submission.
- Existing pharmacist review and high-alert medication controls remain authoritative.
- All recommendations are advisory and require pharmacist/clinician review.
- Generic audit metadata contains no medication narratives, patient identifiers, prompts or model output.

## Phase 4 exclusions
No e-prescribing, pharmacy-management system, dispensing, medication-administration, insurer formulary or external drug-database integration. These require separately approved partner specifications and Phase 4 integration work.

## Phase 5 verification
Authorization, source eligibility, medication snapshot integrity, evidence freshness, missing-context handling, review lifecycle, tenant isolation, migration and downgrade scenarios are recorded in `docs/TEST_REGISTER_PHASE_5.md`. Backend tests remain deferred to Phase 5.
