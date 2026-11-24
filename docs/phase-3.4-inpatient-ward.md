# Phase 3.4 — Inpatient & Ward Management

## Implemented scope

This milestone adds the inpatient admission lifecycle and ward/bed inventory. It does not replace the Emergency, ICU, Theatre, Maternity or Pediatrics modules; those will add their own specialty workflows.

### Workflows

1. Create hospital-scoped wards linked to an active department.
2. Register beds within a ward, with bed type, isolation capability and status.
3. Request an inpatient admission from an authorized clinician's active source encounter.
4. Create a separate inpatient encounter in `admission_requested` state; the request is not an accepted admission or occupied bed.
5. A clinician in the destination ward department accepts the request.
6. A ward/bed manager assigns an available compatible bed; this changes the admission to `admitted`, the bed to `occupied` and the inpatient encounter to `in_progress`.
7. Authorized ward managers assign nurses/clinicians to the inpatient encounter through patient-care assignments.
8. The assigned clinician records a discharge summary. The bed assignment is released and the bed moves to `cleaning`.
9. A ward/bed manager marks the bed `available` only after cleaning.
10. Pending requested/accepted admissions can be cancelled by authorized ward managers.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/inpatient/wards` | Create a ward |
| GET | `/api/v1/inpatient/wards` | List wards within role/department scope |
| POST | `/api/v1/inpatient/wards/{ward_id}/beds` | Register a bed |
| GET | `/api/v1/inpatient/wards/{ward_id}/beds` | List beds and status |
| POST | `/api/v1/inpatient/admissions` | Request admission from an assigned source encounter |
| GET | `/api/v1/inpatient/admissions` | List accessible admissions, including the clinician's own requests |
| GET | `/api/v1/inpatient/admissions/{admission_id}` | Read an accessible admission |
| POST | `/api/v1/inpatient/admissions/{admission_id}/accept` | Clinician accepts the admission |\n| POST | `/api/v1/inpatient/admissions/{admission_id}/cancel` | Cancel a pending admission |
| POST | `/api/v1/inpatient/admissions/{admission_id}/cancel` | Cancel a pending admission |
| POST | `/api/v1/inpatient/admissions/{admission_id}/bed-assignment` | Assign an available bed |
| POST | `/api/v1/inpatient/admissions/{admission_id}/care-team` | Assign a nurse or clinician to the encounter |
| POST | `/api/v1/inpatient/admissions/{admission_id}/discharge` | Clinician discharge and bed release |
| POST | `/api/v1/inpatient/beds/{bed_id}/ready` | Mark a cleaned bed available |

## State and safety boundaries

- Admission request, clinical acceptance, bed assignment and discharge are distinct state transitions.
- A requested or accepted admission does not mean the patient is physically admitted.
- Partial unique indexes prevent more than one requested/accepted/admitted inpatient admission per patient, more than one active bed assignment per bed and more than one active bed per admission.
- Bed assignment locks the bed and admission rows and validates ward compatibility before committing.
- ICU beds require critical-care or high-dependency bed types; maternity and pediatric wards apply their corresponding bed-type restrictions.
- Discharge requires an assigned clinician and a discharge summary. The bed enters cleaning and cannot be allocated again until marked ready.
- Patient-care assignments are required before nursing/clinical staff can access the inpatient encounter through their respective modules.
- Hospital RLS and composite foreign keys bind patient, encounter, ward, bed and admission records to the same hospital.
- No automatic bed selection, clinical admission decision, transfer coordination or AI-generated discharge plan is performed.

## Deferred integrations

- Ward rounds, nursing observation schedules, shift rosters, medication administration and inpatient medication orders.
- Specialty workflows for ICU, surgery, maternity, pediatrics and emergency.
- Inter-hospital transfer acceptance, ambulance dispatch and live tracking.
- Bed cleaning/maintenance task assignment and equipment integration.
- Billing, insurance authorization and clinical documentation exchange.

All lifecycle, concurrency, tenant, assignment, bed compatibility, discharge and audit verification is listed in the Phase 5 Test Register. Tests have not been executed for this milestone.
