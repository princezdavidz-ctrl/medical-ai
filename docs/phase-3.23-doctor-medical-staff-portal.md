# Phase 3.23 — Doctor & Medical Staff Portal

## Scope
A role-aware clinical staff workspace for verified professional profiles, patient care-team assignments, scoped patient overviews and an assigned work queue. It complements—not replaces—the clinical modules that create notes, orders, results, prescriptions, admissions and procedures.

## Clinical identity
- Staff submit a clinical profile linked to their own active HR employee record.
- A hospital administrator, medical director or HR manager independently verifies or rejects credentials using protected vault evidence.
- Verified profiles may be suspended with a recorded reason and reinstated only after independent administrator review with new evidence. Expired-license profiles may be resubmitted and must pass credential verification again. A suspended, unverified or expired-license profile cannot be assigned to a patient or use care-team patient views.
- Registration numbers are unique within a hospital. Regulator verification is manual; no external licensing authority is queried.

## Patient care team
- Authorized clinical administrators, department heads and designated clinical leads assign verified staff to a patient and care role.
- Assignments are hospital-scoped, optionally department-bound, time-limited when an end timestamp is supplied, and cannot be self-assigned.
- Access scopes are limited to profile, encounters, laboratory results and medications. The profile scope is mandatory for staff-portal patient directory and overview access.
- Assignment end/revocation is recorded. Expired assignments are excluded from access and are closed when renewed.
- A verified clinical profile and active HR employment are rechecked on every care-team patient access.

## Work queue
Staff can create tasks for an active employee. Patient-linked tasks require an active care-team assignment for the assignee. Lab-review and medication-review tasks additionally require the corresponding patient data scope. Tasks move through open, in-progress, completed or cancelled states; completed tasks retain actor/time and optional completion note.

## API
- `GET /api/v1/staff-portal/me`
- `GET/POST /api/v1/staff-portal/clinical-profile`
- `GET /api/v1/staff-portal/clinical-profiles`
- `POST /api/v1/staff-portal/clinical-profiles/{profile_id}/decision`
- `POST /api/v1/staff-portal/clinical-profiles/{profile_id}/suspend`
- `POST /api/v1/staff-portal/care-team`
- `GET /api/v1/staff-portal/patients`
- `GET /api/v1/staff-portal/patients/{patient_id}/overview`
- `GET /api/v1/staff-portal/patients/{patient_id}/care-team`
- `POST /api/v1/staff-portal/care-team/{assignment_id}/end`
- `GET/POST /api/v1/staff-portal/tasks`
- `PATCH /api/v1/staff-portal/tasks/{task_id}`
- `GET /api/v1/staff-portal/dashboard`

## Clinical safety and boundaries
- Patient overview returns only scoped patient demographics, encounters, finalized laboratory results and medication orders.
- Critical results are visible to authorized treating clinicians so they can review and act; the patient portal has the separate clinician-acknowledgement release gate.
- This portal does not itself sign clinical notes, prescribe, order tests, perform medication reconciliation, book appointments, manage rosters or execute treatment. Those remain in their clinical modules.
- Care-team access is enforced within this portal. Phase 4 must integrate these assignments into existing patient-facing clinical API authorization before care-team assignment is treated as a universal access boundary.
- No cross-hospital access is granted. Record sharing remains request-based and consent-gated.

## Phase 5 verification
Automated tests are deferred. Verify credential independence, role authorization, expiry/suspension handling, care-team scope, patient tenant isolation, task assignment/state transitions, critical-result visibility to clinicians and append-only access/audit events.
