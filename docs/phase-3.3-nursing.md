# Phase 3.3 — Nursing

## Scope implemented

Nursing workflows are encounter-scoped and available only to authenticated nursing staff with an active hospital membership, a department assignment matching the encounter, and a current patient-care assignment for that exact patient and encounter.

### Workflows

1. **Nursing assessment** — admission, shift, focused and discharge assessment types; general condition, mental status, mobility, skin, pain, manually assessed fall/pressure-injury risk levels and nursing concerns.
2. **Nursing observations** — append-only vital observations, consciousness, oxygen delivery, intake/output and timestamped notes. Broad numeric bounds are data-quality checks, not clinical reference ranges or interpretations.
3. **Nursing notes** — progress, shift handover, incident and discharge notes signed at creation. No update/delete endpoint is provided.
4. **Nursing care plans** — nursing diagnosis, goals and interventions with active/completed/cancelled lifecycle.
5. **Care-plan reviews** — append-only evaluation events; an achieved outcome completes the plan. Escalated and other outcomes remain review history.
6. **Encounter nursing record view** — retrieves scoped assessments, observations, notes, plans and reviews with an access audit event.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/nursing/encounters/{encounter_id}/assessments` | Record nursing assessment |
| POST | `/api/v1/nursing/encounters/{encounter_id}/observations` | Record timestamped observations |
| POST | `/api/v1/nursing/encounters/{encounter_id}/notes` | Sign a nursing note |
| POST | `/api/v1/nursing/encounters/{encounter_id}/care-plans` | Create care plan |
| POST | `/api/v1/nursing/care-plans/{care_plan_id}/reviews` | Append care-plan evaluation |
| POST | `/api/v1/nursing/care-plans/{care_plan_id}/close` | Complete or cancel care plan |
| GET | `/api/v1/nursing/encounters/{encounter_id}/records` | Read scoped nursing record set |

## Security and data integrity

- No nursing endpoint accepts an arbitrary patient ID. Patient identity is derived from the authorized encounter.
- The staff member must have an active nursing role, active department membership and active care assignment for the exact encounter.
- Composite foreign keys bind patient, encounter and hospital identifiers so cross-tenant or mismatched-patient records cannot be persisted.
- All nursing tables enforce hospital RLS.
- Audits capture actor, action and resource identifiers, not note text, vital values or sensitive clinical narratives.
- Nursing records are append-only through the exposed API; corrections/addenda require a separately governed workflow.
- No AI-generated care plan, risk score, diagnosis, clinical interpretation or autonomous action is enabled.

## Deliberately deferred

- Medication administration records (MAR) are deferred until the Pharmacy & Medication Management module provides a verified prescription/order model and medication safety checks. Nurses must not record an administration against free-text or unverified medication instructions.
- Inpatient bed/ward assignment, observation schedules and shift roster integration belong to Inpatient & Ward Management and Staff Scheduling.
- Device integrations, monitor ingestion and clinical alert thresholds are deferred to the integration phase and clinical governance.
- Nursing workflows do not replace clinician diagnosis, prescribing or escalation protocols.

All workflow, assignment, RLS, privacy, observation, note-signing, care-plan and concurrency verification is listed in the Phase 5 Test Register. No tests were executed for this milestone.
