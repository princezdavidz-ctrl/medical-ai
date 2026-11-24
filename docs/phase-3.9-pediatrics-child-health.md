# Phase 3.9 — Pediatrics & Child Health

## Scope implemented

Pediatrics provides encounter-scoped child-health records for patients under 18 at the time the record is opened. Each record is linked to one hospital patient and one active encounter.

### Workflows

1. **Pediatric encounter record** — an assigned pediatric clinician or nurse opens a record for a patient with a verified date of birth, an active patient status, an in-progress encounter and a matching pediatric department.
2. **Growth observations** — staff append measured or reported weight, height/length, head circumference, mid-upper-arm circumference and temperature observations with source and observation time.
3. **Developmental screening record** — staff record the instrument name/version, developmental domain, manually assessed outcome, referral recommendation and notes.
4. **Immunization history** — staff record administered, externally reported, deferred, declined or unknown immunization history, including provenance, date, dose label and opaque batch reference where available. This is a history record, not a vaccine order or administration authorization.
5. **Signed pediatric notes** — assigned staff create immutable assessment, progress, handover, discharge or other notes.
6. **Record closure** — an assigned pediatric team member closes the pediatric record only after the linked encounter is no longer in progress. Closed records remain read-only.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/pediatrics/encounters/{encounter_id}/records` | Open a pediatric record |
| GET | `/api/v1/pediatrics/records/{record_id}` | Read pediatric record and histories |
| POST | `/api/v1/pediatrics/records/{record_id}/growth-observations` | Append growth/measurement observation |
| POST | `/api/v1/pediatrics/records/{record_id}/developmental-screenings` | Record manual developmental screening |
| POST | `/api/v1/pediatrics/records/{record_id}/immunization-history` | Record immunization history/provenance |
| POST | `/api/v1/pediatrics/records/{record_id}/notes` | Sign an immutable pediatric note |
| POST | `/api/v1/pediatrics/records/{record_id}/close` | Close record after encounter completion |

## Authorization, privacy and data integrity

- Every request requires an active hospital membership with a pediatric/child-health role and department matching the record.
- Clinical access requires an active care assignment for the exact hospital, patient, encounter and department.
- Record creation requires an active patient, date of birth, patient age below 18 on the hospital server date, an in-progress same-patient encounter and a matching active department.
- A unique hospital/encounter constraint prevents duplicate pediatric records for one encounter.
- Composite foreign keys bind the pediatric record to the same hospital, patient, encounter and department.
- All pediatric tables enforce hospital row-level security.
- Growth observations, screening results, immunization history and signed notes are append-only through the API. No edit/delete endpoints are exposed.
- Audit events record actor, action and resource identifiers, not measurements, screening notes, immunization notes or clinical narrative.
- Guardian access, proxy portal permissions and consent evidence are governed by the patient/consent and portal modules; this API does not grant guardian access.

## Clinical safety boundaries

- Measurements use broad data-quality bounds only. No BMI, growth percentile, z-score, centile, nutritional classification or growth trajectory is calculated.
- Developmental screening outcomes are entered by staff. No screening instrument is executed or scored by the system, and no diagnosis is inferred.
- Immunization history is documentation only. No vaccine schedule, due-date calculation, reminder, vaccine order, stock reservation, dosing instruction or administration authorization is generated.
- A reported immunization is not represented as a facility-administered dose. Caregiver-reported source cannot claim facility administration.
- No pediatric diagnosis, prescribing, medication dosing, automated triage, clinical alert threshold or AI-generated treatment advice is enabled.
- No live patient data is seeded or approved for development.

## Deferred integrations

- Kenya national immunization registry and child health book/reporting interfaces.
- Vaccine catalog, stock, cold-chain monitoring, ordering and administration records integrated with Pharmacy/Inventory.
- Approved growth standards, developmental instruments and clinical escalation pathways after jurisdiction-specific clinical governance.
- Guardian/proxy portal access and consent integration.
- Laboratory, radiology, inpatient, emergency, ICU and referral/transfer workflows remain owned by their respective modules.

All pediatric age, assignment, department, tenant, growth, developmental, immunization provenance, note-signing and closure checks are listed in the Phase 5 Test Register. Tests have not been executed for this milestone.
