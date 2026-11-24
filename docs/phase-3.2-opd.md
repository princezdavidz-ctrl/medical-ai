# Phase 3.2 — OPD (Outpatient Department)

## Implemented workflow

1. Registration creates an OPD visit and a linked `Encounter`.
2. The visit receives a random, hospital/day-scoped queue token.
3. Reception or designated triage staff marks arrival.
4. A department-scoped triage nurse records the manual triage level, complaint, red-flag note and available observations/vitals.
5. The visit enters the department waiting queue. Emergency and urgent priorities sort ahead of routine visits.
6. An assigned clinician starts consultation, records a signed consultation note and records structured/free-text diagnoses.
7. The clinician records a disposition: discharged, admission requested, referred or transfer requested. A patient who leaves before consultation can be recorded as left without being seen.
8. Encounter assignments remain active for a limited 24-hour post-closure review window, then expire by timestamp.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/opd/visits` | Register a new OPD visit |
| GET | `/api/v1/opd/visits` | View a role-scoped OPD queue |
| GET | `/api/v1/opd/visits/{visit_id}` | Read visit, patient summary, triage, consultation and diagnoses |
| POST | `/api/v1/opd/visits/{visit_id}/arrive` | Record patient arrival |
| POST | `/api/v1/opd/visits/{visit_id}/triage` | Record nurse-led triage and observations |
| POST | `/api/v1/opd/visits/{visit_id}/consultation/start` | Assign/start clinician consultation |
| POST | `/api/v1/opd/visits/{visit_id}/consultation/complete` | Sign the consultation note |
| POST | `/api/v1/opd/visits/{visit_id}/diagnoses` | Record a diagnosis and certainty |
| POST | `/api/v1/opd/visits/{visit_id}/disposition` | Close the visit with a disposition |
| POST | `/api/v1/opd/visits/{visit_id}/cancel` | Cancel a registered visit before arrival |

## Role and department scope

- Registration/reception/medical-records roles can create visits, mark arrivals and view the hospital OPD queue.
- Triage nurses can view open queue items in their department and record triage.
- Clinicians can view visits only when assigned to the encounter and within their active department membership.
- Only clinician roles can start/complete consultations and record diagnoses.
- Triage staff may record a patient leaving without being seen; other dispositions require the assigned clinician.
- Hospital admin/director/system admin can administer and view queues but cannot sign clinical notes as a substitute for a clinician.
- Minimal patient identity is returned in OPD queue/detail responses; clinical record access remains assignment-scoped.

## Clinical safety boundaries

- Triage level and red-flag presence are selected by clinical staff. No automated triage score or AI-generated urgency is applied.
- Vitals have broad data-quality bounds; these are not diagnostic reference ranges and do not interpret a result.
- Red-flag presence requires an escalation note and cannot be paired with routine/non-urgent triage.
- Consultation notes are signed at completion and have no edit endpoint. Corrections/addenda require a separately governed workflow.
- Diagnosis text can be recorded without a code. A concept ID is accepted only when linked to current approved knowledge; no diagnosis catalog is seeded.
- No AI diagnosis or treatment recommendation is enabled in OPD.
- `admission_requested` is only an admission request, not an accepted admission or confirmed bed.
- `referred` and `transfer_requested` are dispositions only; they do not claim that a receiving hospital accepted a referral, records were shared or transport was arranged.
- Lab, radiology, pharmacy, billing and inpatient orders are owned by their respective later modules; OPD does not create substitute orders.

## Known limitations and next integrations

- Appointment scheduling and source referral/transfer validation are not implemented; visit type is a classification only.
- No clinical note addendum or triage reassessment workflow is exposed yet.
- No lab/radiology/pharmacy orders or inpatient bed confirmation.
- The patient consent authorization service is available for purpose-scoped data sharing, but OPD internal-care routes do not replace legal-basis review or downstream HIE consent checks.
- Hospital timezone-aware queue dates and token-display conventions require deployment configuration.
- No real patient data is approved for development.

All OPD state, access, tenant, queue, clinical-note, triage and disposition checks are recorded in `docs/TEST_REGISTER_PHASE_5.md`.
