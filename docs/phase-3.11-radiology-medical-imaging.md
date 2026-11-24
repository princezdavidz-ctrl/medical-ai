# Phase 3.11 — Radiology & Medical Imaging

## Scope implemented

Radiology provides a governed hospital imaging-procedure catalog and encounter-linked workflow for imaging orders, scheduling, study acquisition, report entry, independent report verification and critical-finding acknowledgement.

### Workflow

1. **Procedure catalog drafting** — radiology managers/directors create hospital-specific procedure definitions with code, name, modality, body region, contrast policy and preparation instructions. New definitions remain drafts and cannot be ordered.
2. **Independent catalog approval** — a different radiologist, radiology director or imaging supervisor approves a draft. The approver must have a nonblank professional-registration value recorded on the hospital membership. The platform does not independently verify that credential. Authorized registered approvers can retire active definitions with an attributed reason.
3. **Clinician order** — an authorized clinician with an active patient-care assignment places an imaging order against an in-progress encounter. Patient identity is derived from the encounter; the client cannot submit an unrelated patient ID.
4. **Radiology work queue** — imaging staff see orders routed to their own radiology department, with STAT then urgent then routine priority and minimum-necessary patient identity.
5. **Scheduling** — radiology staff assign an accession number and a timezone-aware future appointment time. Only one study can be scheduled per order.
6. **Study acquisition** — an assigned radiology staff member starts the study and later marks acquisition complete. An opaque PACS system reference and study UID may be recorded; no image files are uploaded or interpreted by this module.
7. **Preliminary report** — a radiologist or radiology resident records findings, impression and any manually identified critical flag/note after the study is complete.
8. **Independent report verification** — a different registered radiologist, radiology director or imaging supervisor finalizes the report. Final reports are immutable through this API.
9. **Critical-finding acknowledgement** — a final report manually marked critical requires an acknowledgement record from a clinician with an active assignment to the ordering encounter.
10. **Cancellation** — an order can be cancelled before acquisition starts. A scheduled study is also marked cancelled. Orders cannot be cancelled after acquisition begins.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/radiology/procedure-definitions` | Create a draft procedure definition |
| POST | `/api/v1/radiology/procedure-definitions/{definition_id}/approve` | Independently approve a procedure definition |
| POST | `/api/v1/radiology/procedure-definitions/{definition_id}/retire` | Retire an active definition with reason |
| GET | `/api/v1/radiology/procedure-definitions` | List active procedure definitions in permitted scope |
| POST | `/api/v1/radiology/encounters/{encounter_id}/orders` | Place an assigned clinician imaging order |
| GET | `/api/v1/radiology/orders` | View the department imaging queue |
| GET | `/api/v1/radiology/orders/{order_id}` | Read order, patient summary, study and report |
| POST | `/api/v1/radiology/orders/{order_id}/schedule` | Schedule study and assign accession number |
| POST | `/api/v1/radiology/studies/{study_id}/start` | Start acquisition |
| POST | `/api/v1/radiology/studies/{study_id}/complete` | Complete acquisition and optionally record PACS references |
| POST | `/api/v1/radiology/studies/{study_id}/reports` | Enter a preliminary report |
| POST | `/api/v1/radiology/reports/{report_id}/verify` | Independently verify/finalize report |
| POST | `/api/v1/radiology/reports/{report_id}/acknowledge-critical` | Record assigned clinician acknowledgement |
| POST | `/api/v1/radiology/orders/{order_id}/cancel` | Cancel an eligible order with reason |

## Authorization, tenant isolation and audit

- Procedure catalog actions are restricted to radiology catalog roles and the relevant imaging department.
- Catalog approval and report verification require a different user from the creator/author.
- Approvers/verifiers must have a nonblank professional-registration value recorded. This is a data-presence check, not independent professional credential verification.
- Orders require an active clinician role, an in-progress encounter, active patient status and an active assignment to the exact patient/encounter/ordering department.
- Radiology staff access only orders routed to their own imaging department.
- Ordering clinicians can read/acknowledge only orders within their department and active patient-care assignment.
- Composite foreign keys bind orders to the same hospital, patient, encounter, ordering department, imaging department and procedure definition.
- All radiology tables enforce hospital row-level security.
- Audit metadata records actions, actors, resource IDs and non-clinical state values; findings, impressions, clinical indications and patient narratives are not copied into audit metadata.
- Queue/order responses expose only MRN and given/family name for patient identification.

## Clinical safety boundaries

- No procedure catalog is seeded. Each hospital must govern and approve its own catalog.
- Contrast policy is catalog metadata only. This module does not prescribe contrast, medication, dose, renal screening or premedication.
- No DICOM image upload, PACS query/retrieve, image rendering, automated segmentation, measurement, detection, diagnosis or AI interpretation is enabled.
- PACS references are opaque identifiers only; their presence does not prove that images were transmitted or are retrievable.
- Critical findings are manually flagged by the reporting clinician. No automated critical threshold, notification or escalation decision is generated.
- Critical acknowledgement is a manual audit record; it does not prove a phone call or other notification was delivered.
- Final reports cannot be edited or amended through this API. A governed addendum workflow remains future work.
- No live patient or imaging data is seeded.

## Deferred integrations

- DICOMweb/PACS, modality worklist, HL7 v2 and FHIR ImagingStudy/DiagnosticReport/ServiceRequest.
- DICOM image storage, image viewer, image transfer, accession reconciliation and external PACS acknowledgement.
- Contrast safety screening, medication/pharmacy integration, radiation dose monitoring and device interfaces.
- Approved radiology reporting templates, structured findings, coding and critical-finding escalation pathways.
- AI radiology assistance only through the central AI platform after separate evaluation and clinical release approval.

All procedure catalog, role/assignment, order, schedule, acquisition, PACS reference, report, verification, critical acknowledgement, cancellation, tenant isolation and audit checks are listed in the Phase 5 Test Register. Tests have not been executed for this milestone.
