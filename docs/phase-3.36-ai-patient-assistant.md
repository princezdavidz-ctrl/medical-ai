# Phase 3.36 — AI Patient Assistant

## Scope
A patient-portal-only, evidence-grounded education endpoint for general health questions, appointment preparation, and plain-language explanations of general clinician-approved medication instructions.

## Authorization and privacy
- Requires an active authenticated patient-portal identity and a verified, unexpired portal link for the selected patient.
- The portal link must explicitly include the `ai_assistant` access scope.
- Requires a current, granted, unexpired, non-withdrawn `patient_ai_assistance` consent with `ai_processing=true`.
- Direct identifiers in free text are rejected.
- The endpoint does not retrieve or inject EHR chart data, medication lists, diagnoses, laboratory results or appointment details.
- Audit events retain metadata only; question and answer text are not stored by this workflow.

## AI and clinical safety
- Uses the central medical-information capability and approved, current knowledge retrieval.
- Requires a configured local provider; hosted processing is never attempted for this patient portal endpoint.
- Plain-language education only. No diagnosis, prescribing, individualized treatment decision, dose change, medication order, test interpretation or clinical record write.
- Urgent or rapidly worsening symptoms are directed to immediate emergency assessment.
- Citations are returned with the answer; missing/unsafe evidence results in a fail-closed response.
- Clinical use remains disabled. The response is not a substitute for a clinician or pharmacist.

## Explicit exclusions
Patient-specific chart summarization, personal laboratory interpretation, personal medication reconciliation, persistent conversation history, appointment booking and clinical messaging remain separate workflows requiring additional consent, patient-context authorization and Phase 4 integrations.
