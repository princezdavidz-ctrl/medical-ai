# Phase 2B.13 — Authorized patient-context adapter

## Authorization requirements

Patient context is not available merely because a caller supplies a patient UUID. The adapter requires all of the following within the selected hospital context:

1. An active hospital membership for the requesting staff user.
2. A clinical role in the explicit patient-context allow-list.
3. An active, time-valid patient care assignment linking that staff user to the patient (and, where specified, the encounter).
4. An active encounter for the patient in the same hospital.
5. Explicit, unwithdrawn, unexpired consent for the exact purpose `clinical_ai_assistance`, including `ai_processing=true` and both `demographics` and `encounter` data categories.
6. An approved capability and configured local provider before the patient record is queried for AI context.

Missing or invalid conditions fail closed. There is no emergency-access bypass in this adapter.

## Minimum-necessary context

The adapter currently passes only:
- age in years, derived from date of birth;
- administrative sex;
- encounter type and status;
- department name, when available.

It deliberately excludes patient name, medical record number, phone, exact date of birth, staff identifiers, and free-text encounter notes. Free-text notes are excluded until a reviewed PHI-redaction mechanism exists.

## Local-only routing

The API preflights the AI policy and verifies that a local provider is registered before loading patient context. The orchestrator independently evaluates policy with `has_patient_context=true`. In hybrid mode, patient context is local-only. Offline and degraded modes also require local inference. No hosted fallback is attempted.

Patient context is appended to the model's evidence context as untrusted clinical data, explicitly marked as data rather than instructions. The standard approved-evidence retrieval and citation checks still apply. The API response continues to require clinician review and reports clinical use disabled.

## Database and audit

- `patient_care_assignments` is hospital-scoped and protected by forced PostgreSQL RLS.
- Assignment rows include staff, patient, hospital, optional encounter/department, reason, validity and revocation state.
- Denied patient-context requests create an audit event with a minimal reason code and the patient resource reference.
- Successful AI request audit metadata records the consent, assignment and encounter references, not the prompt or patient context values.

## Operational limitations

- This milestone does not add a staff-facing assignment creation/revocation API. Assignment administration belongs in the Phase 3 patient and staff-management workflows; until then, records must be created only through a trusted, authorized administrative process.
- Consent capture/withdrawal workflows remain incomplete.
- Role names are currently an explicit allow-list; the broader permission matrix is still to be completed.
- No clinical notes, lab results, medication lists, imaging reports or other detailed patient data are included yet.
- No patient-context data is sent to a hosted model.
- The adapter is not clinical certification and does not authorize patient-care use.
