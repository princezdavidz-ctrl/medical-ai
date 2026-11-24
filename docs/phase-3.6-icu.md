# Phase 3.6 — Intensive Care Unit (ICU)

## Implemented scope

ICU stays are opened only for an already admitted inpatient whose active bed assignment is in an active ICU ward. The ICU workflow is linked to the Inpatient & Ward module rather than creating a separate admission or bed record.

### Workflows

1. An assigned ICU clinician starts an ICU stay against an admitted inpatient admission and its active occupied ICU bed.
2. Assigned ICU nurses and clinicians append timestamped observations, including vital signs, oxygen/ventilation support descriptors, fluid balance and individual Glasgow Coma Scale components.
3. Assigned staff append care events for assessments, interventions, procedures, airway support, ventilation changes and handovers.
4. Assigned staff sign daily review, progress, handover and incident notes.
5. An ICU clinician can request stepdown. This records the request and reason but does not claim that a ward bed is accepted or that the patient has left ICU.
6. The ICU stay can be closed after the Inpatient module has completed the hospital discharge workflow.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/icu/stays` | Start an ICU stay from an admitted inpatient with an occupied ICU bed |
| GET | `/api/v1/icu/stays` | List ICU stays visible to assigned staff |
| GET | `/api/v1/icu/stays/{stay_id}` | Read ICU stay and its records |
| POST | `/api/v1/icu/stays/{stay_id}/observations` | Append timestamped ICU observations |
| POST | `/api/v1/icu/stays/{stay_id}/events` | Append ICU care events |
| POST | `/api/v1/icu/stays/{stay_id}/notes` | Sign ICU progress notes |
| POST | `/api/v1/icu/stays/{stay_id}/stepdown-request` | Record a clinician stepdown request |
| POST | `/api/v1/icu/stays/{stay_id}/close` | Close the ICU stay after inpatient discharge |

## Authorization and integrity

- ICU nurses and clinicians require active hospital membership, ICU department membership and an active patient-care assignment to the inpatient encounter.
- Only ICU clinicians can start a stay, request stepdown or close a stay.
- ICU start verifies admitted status, an active occupied bed assignment, an active ICU ward, and a matching inpatient encounter/department.
- Composite foreign keys bind ICU stay to the same hospital, patient, encounter, inpatient admission, bed assignment, ward and department.
- A partial unique index prevents more than one active/stepdown-requested ICU stay for the same admission.
- ICU observations, care events and notes are append-only through the exposed API.
- Hospital RLS applies to all ICU tables.
- Audit events record actor, action and resource identifiers without copying clinical narratives or observation values.

## Clinical safety boundaries

- Vital observations have broad data-quality limits only; they are not diagnostic thresholds or automated alarms.
- Glasgow Coma Scale eye, verbal and motor components are recorded separately; the module does not calculate or interpret a score.
- No automatic severity score (including APACHE/SOFA), diagnosis, prognosis, ventilator recommendation, medication dose, vasopressor order or treatment recommendation is generated.
- Oxygen and ventilation descriptors are documentation fields, not device control.
- Stepdown request is not a completed transfer and does not release the ICU bed.
- ICU AI capabilities remain disabled unless separately approved through central AI evaluation and clinical release governance.

## Deferred integrations

- Bed-to-bed stepdown/transfer acceptance and ICU bed release after confirmed ward placement.
- Ventilator/monitor/device ingestion, alarm routing and clinical threshold governance.
- Medication orders, infusion/vasopressor management and medication administration through Pharmacy.
- Renal replacement therapy, dialysis workflows and specialty ICU procedures.
- ICU staffing, shift rosters, multidisciplinary rounds and specialty dashboards.

All ICU admission, bed, assignment, observation, GCS, stepdown, discharge, RLS and audit checks are listed in the Phase 5 Test Register. Tests have not been executed for this milestone.
