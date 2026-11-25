# Phase 3.26 — Telemedicine & Remote Care

## Purpose

Provide the hospital-side workflow for scheduling and conducting a remote clinical consultation. The module manages the clinical session lifecycle and safety gates. It is transport-neutral: it does not claim to provide a live video call until a supported video provider is integrated in Phase 4.

## Capabilities

- Schedule a remote consultation for a hospital patient with an active, verified clinical provider, active department, exact patient telemedicine consent and a rostered staff shift covering the appointment.
- Prevent overlapping sessions for the same patient or provider. Patient and employee row locks serialize scheduling requests.
- Department heads and nurse managers are restricted to their active department. Telemedicine coordinators, appointment schedulers and hospital-level administrators have their permitted hospital-wide scheduling scope.
- Record patient readiness with encrypted-vault references for current location and emergency contact, plus explicit identity confirmation, privacy confirmation and emergency-plan acknowledgement.
- Recheck the exact telemedicine consent at scheduling, patient readiness and session start. The consent must be granted, unexpired, not withdrawn, declare a lawful basis, include clinical_records and permit telemedicine use.
- Start only within the appointment window, with a verified active provider, active roster coverage and active patient care-team assignment. Starting creates a telemedicine encounter.
- Create signed, append-only consultation, assessment, plan, follow-up, safety-plan and referral notes linked to the encounter. Only the assigned provider can author session notes.
- Complete a session only after at least one signed note exists; close the linked encounter at the same time.
- Cancel pre-start sessions with a reason and mark sessions no-show only after the scheduled end time.
- Keep an append-only session event ledger and audit sensitive session/note reads.

## Safety and authorization

- Provider must have active hospital membership, active employment, active user account, verified clinical profile, supported clinical role and an unexpired license.
- Provider must have an active Staff Management & Scheduling shift covering the full scheduled session.
- The provider must be assigned to the patient's active care team with encounter access before the session can start.
- The patient's exact consent record is checked by ID; a different authorization record cannot silently substitute for the supplied consent.
- Before a session becomes patient-ready, staff must record the encrypted references for patient location and emergency contact and attest identity, privacy and emergency-plan checks.
- A consent withdrawal before start prevents the consultation from starting. If consent is withdrawn after the consultation has started, the provider can still document and close the encounter so the clinical record is not left incomplete.
- Clinical notes and session events cannot be updated or deleted through the database trigger. Corrections use separate addenda or amendment workflows.
- No session recording is performed by this module.

## API

Base prefix: /api/v1/telemedicine

| Method | Path | Purpose |
|---|---|---|
| POST | /sessions | Schedule a remote consultation |
| GET | /sessions | List permitted session schedules |
| GET | /sessions/{session_id} | Read a permitted session |
| POST | /sessions/{session_id}/patient-ready | Record identity, privacy and emergency readiness |
| POST | /sessions/{session_id}/start | Start session and create telemedicine encounter |
| POST | /sessions/{session_id}/notes | Create a signed clinical note |
| GET | /sessions/{session_id}/notes | Read notes with provider/care-team access |
| POST | /sessions/{session_id}/complete | Complete session and close encounter |
| POST | /sessions/{session_id}/cancel | Cancel before start with reason |
| POST | /sessions/{session_id}/no-show | Mark no-show after scheduled end |

## Integration boundaries

- Live video/audio, waiting-room media transport, meeting links, call quality telemetry and provider credentials are Phase 4 integrations.
- Patient-side booking, patient-side readiness attestation, OTP/identity verification, notifications, rescheduling and calendar integrations are Phase 4 integrations.
- Clinical notes are retained in the telemedicine encounter workflow; publishing signed notes into the Medical Records document index is a Phase 4 adapter.
- Prescriptions, laboratory orders, referrals, billing and follow-up appointments continue to use their respective department modules and will be connected in Phase 4.
- Remote location and emergency contact values are not stored as raw text in session rows; only opaque vault references are retained. The secure vault adapter is a Phase 4 dependency.

## Migration and verification

Migration: 0043_telemedicine, after 0042_patient_records. The three tables are hospital-scoped with RLS; signed notes and session events have database append-only triggers.

Backend tests were not run during development, per project direction. All authorization, consent, roster, scheduling concurrency, emergency readiness, encounter, note and lifecycle checks are in docs/TEST_REGISTER_PHASE_5.md.
