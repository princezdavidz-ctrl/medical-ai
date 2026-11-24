# Phase 3.8 — Maternity & Newborn Care

## Implemented scope

The maternity module manages a pregnancy episode linked to a hospital patient and active encounter, antenatal visits, labor observations, delivery, newborn records, postpartum observations and signed maternity notes.

### Workflow

1. An assigned midwife or obstetric clinician creates a pregnancy episode. Gravida, para, pregnancy number, LMP and estimated due date are recorded as supplied; the system does not calculate or infer them.
2. The maternity team records antenatal visits and manually documented gestational age, maternal observations, fetal heart rate and fundal height.
3. A midwife or obstetric clinician opens a labor record. Assigned maternity staff append timestamped labor observations, including labor stage, cervical dilation, fetal heart rate, contractions and maternal observations.
4. Vaginal or assisted delivery is recorded against the labor record. Cesarean delivery must link to a same-patient, same-encounter surgical case in progress, recovery or completed state.
5. Planned cesarean delivery without a labor record is supported and must also link to the matching surgical case.
6. Each newborn is recorded separately, allowing multiple births per delivery. Birth outcome, sex, measurements, resuscitation and manually entered Apgar scores at 1, 5 and 10 minutes are stored.
7. Registration staff link a newborn record to an existing patient record after verifying date of birth and sex. The maternity module does not create patient MRNs itself.
8. Assigned neonatal staff append newborn observations. Assigned maternity staff append maternal postpartum observations.
9. Obstetric clinicians can record pregnancy ending without delivery, using a structured reason and signed note. Postpartum episodes can be closed with a reason after delivery.
10. Maternity and neonatal team assignments can cross department boundaries, but require active same-hospital membership and an explicit encounter assignment.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/maternity/episodes` | Create pregnancy episode |
| GET | `/api/v1/maternity/episodes` | List assigned maternity episodes |
| GET | `/api/v1/maternity/episodes/{episode_id}` | Read episode, antenatal, labor, delivery, newborn and postpartum records |
| POST | `/api/v1/maternity/episodes/{episode_id}/team` | Assign maternity or neonatal team member |
| POST | `/api/v1/maternity/episodes/{episode_id}/antenatal-visits` | Record antenatal visit |
| POST | `/api/v1/maternity/episodes/{episode_id}/labor` | Start labor record |
| POST | `/api/v1/maternity/labor/{labor_id}/observations` | Append labor observation |
| POST | `/api/v1/maternity/labor/{labor_id}/delivery` | Record delivery from labor |
| POST | `/api/v1/maternity/episodes/{episode_id}/delivery` | Record planned cesarean without labor |
| POST | `/api/v1/maternity/deliveries/{delivery_id}/newborns` | Record each newborn |
| GET | `/api/v1/maternity/newborns/{newborn_id}` | Read newborn and observation history |
| POST | `/api/v1/maternity/newborns/{newborn_id}/link-patient` | Link to existing patient record |
| POST | `/api/v1/maternity/newborns/{newborn_id}/observations` | Append newborn observation |
| POST | `/api/v1/maternity/episodes/{episode_id}/postpartum-observations` | Append maternal postpartum observation |
| POST | `/api/v1/maternity/episodes/{episode_id}/notes` | Sign maternity note |
| POST | `/api/v1/maternity/episodes/{episode_id}/end-pregnancy` | Record pregnancy ending/loss |
| POST | `/api/v1/maternity/episodes/{episode_id}/close` | Close postpartum episode |

## Authorization, data integrity and privacy

- Episode creation requires an active maternity department, an in-progress encounter for the same patient and an active patient-care assignment.
- Maternity, obstetric and neonatal roles are separate. Each write requires an active same-hospital membership and encounter assignment.
- Explicit maternity team assignment supports cross-department neonatal staff while preserving encounter-level access boundaries.
- One active maternity episode per patient is enforced by a partial unique index. Pregnancy number is unique per patient.
- One labor record and one delivery are permitted per pregnancy episode. A delivery may be linked to a labor record or, for planned cesarean, recorded directly against the episode.
- Composite foreign keys ensure a newborn belongs to the same mother as the delivery and prevent cross-hospital patient links.
- Cesarean delivery must reference a surgical case for the same patient and encounter. The database also enforces that only cesarean records carry a surgical-case link.
- Newborn patient links are unique and must match date of birth and, when known, sex. Stillbirth records cannot be linked to a patient record.
- All maternity tables use hospital RLS. Signed notes and observation histories have no edit/delete API.
- Audit records contain actor, action and resource identifiers, not clinical narratives, fetal observations or newborn measurements.

## Clinical safety boundaries

- Gestational age, LMP, EDD, labor stage, cervical dilation and fetal observations are entered by staff. No automatic gestational-age calculation, partograph scoring, alert threshold, obstetric risk score or fetal interpretation is generated.
- Apgar scores are manually entered; no score is calculated or interpreted.
- Vitals and observations have broad data-quality bounds only. They are not diagnostic reference ranges or treatment triggers.
- No medication dosing, prescriptions, anesthesia medication administration, blood-product orders, neonatal diagnosis, resuscitation device control or AI-generated treatment advice is enabled.
- A pregnancy ending record captures a structured reason and clinician note; it does not replace required local clinical, legal, bereavement or safeguarding workflows.
- Delivery recording does not imply maternal discharge, newborn discharge, inpatient bed transfer or receiving-facility acceptance.

## Deferred integrations

- Maternal admission/bed allocation, theatre recovery/PACU handover and postpartum ward transfer.
- Blood bank, laboratory, ultrasound/radiology, pharmacy and medication administration.
- Full national maternal-child health reporting, immunization schedules and child health book integration.
- Newborn MRN creation and registration automation; this milestone only links an already registered patient.
- Neonatal ICU admission, neonatal referral/transfer, feeding support plans and discharge workflows.
- Locally approved partograph forms, clinical escalation thresholds, obstetric emergency bundles and credential/privilege verification.

All maternity, labor, delivery, cesarean linkage, newborn, postpartum, pregnancy-ending, tenant, access and audit checks are in the Phase 5 Test Register. Tests have not been executed for this milestone.
