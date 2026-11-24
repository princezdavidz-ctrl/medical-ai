# Phase 3.10 — Laboratory & Diagnostics

## Scope implemented

The laboratory module provides a governed hospital test catalog and an encounter-linked workflow for ordering, specimen tracking, result entry, independent verification and critical-result acknowledgement.

### Workflow

1. **Test catalog drafting** — laboratory managers/supervisors create hospital-specific test definitions with code, name, specimen type, method and result unit. New definitions remain drafts and cannot be ordered.
2. **Independent catalog approval** — a different laboratory supervisor, laboratory director or pathologist approves a draft. The approver must have a professional-registration value recorded on the hospital membership. The platform does not independently verify that credential.
3. **Clinician order** — an authorized clinician with an active care assignment places a test order against an in-progress encounter. Patient identity is derived from the encounter; clients cannot submit an unrelated patient ID.
4. **Laboratory work queue** — laboratory staff see orders routed to their own laboratory department, with minimum-necessary patient identity.
5. **Specimen collection and accessioning** — laboratory staff record accession number, catalog-defined specimen type, collector and collection timestamp. A rejected specimen requires a reason; rejected specimens may be recollected. Only one non-rejected specimen may be active per order.
6. **Specimen receipt and processing** — staff move specimens through collected, received and processing states. Invalid state transitions are rejected.
7. **Preliminary result** — a laboratory worker enters exactly one text or numeric result. Numeric units must match the approved test definition. Manual abnormality and critical flags are recorded without automated reference-range interpretation.
8. **Independent verification** — a different laboratory verifier with a recorded professional-registration value changes a preliminary result to final. The final result is immutable through this API.
9. **Critical-result acknowledgement** — a final result manually marked critical requires an acknowledgement record from a clinician with an active assignment to the ordering encounter.
10. **Cancellation** — an order may be cancelled only before any non-rejected specimen remains active. Cancellation requires a reason and actor attribution.

## API routes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/laboratory/test-definitions` | Create a draft test definition |
| POST | `/api/v1/laboratory/test-definitions/{definition_id}/approve` | Independently approve a test definition |
| POST | `/api/v1/laboratory/test-definitions/{definition_id}/retire` | Retire an active definition |
| GET | `/api/v1/laboratory/test-definitions` | List active definitions in permitted scope |
| POST | `/api/v1/laboratory/encounters/{encounter_id}/orders` | Place a clinician test order |
| GET | `/api/v1/laboratory/orders` | View the department laboratory queue |
| GET | `/api/v1/laboratory/orders/{order_id}` | Read order, minimum patient identity, specimens and results |
| POST | `/api/v1/laboratory/orders/{order_id}/specimens` | Record specimen collection or initial rejection |
| POST | `/api/v1/laboratory/specimens/{specimen_id}/receive` | Receive a collected specimen |
| POST | `/api/v1/laboratory/specimens/{specimen_id}/reject` | Reject a collected/received specimen |
| POST | `/api/v1/laboratory/specimens/{specimen_id}/start-processing` | Start laboratory processing |
| POST | `/api/v1/laboratory/specimens/{specimen_id}/results` | Enter a preliminary result |
| POST | `/api/v1/laboratory/results/{result_id}/verify` | Independently verify and finalize a result |
| POST | `/api/v1/laboratory/results/{result_id}/acknowledge-critical` | Record assigned clinician acknowledgement |
| POST | `/api/v1/laboratory/orders/{order_id}/cancel` | Cancel an eligible order with reason |

## Authorization, tenant isolation and audit

- Test catalog actions are restricted to laboratory catalog roles and the relevant laboratory department.
- Test definition approval and final result verification require a different user from the creator/entered-by user.
- The verifier must have a professional-registration value recorded. This is a data-presence check, not independent professional credential verification.
- Orders require an active clinician role, an in-progress encounter, active patient status and an active assignment to the exact patient/encounter/ordering department.
- Laboratory staff access only the queue and orders routed to their own laboratory department.
- Ordering clinicians can read/acknowledge only orders within their department and active patient-care assignment.
- Composite foreign keys bind orders to the same hospital, patient, encounter, ordering department, laboratory department and test definition.
- All laboratory tables enforce hospital row-level security.
- Audit metadata records actions, actors, resource IDs and non-clinical state values; result values, specimen narratives and clinical indications are not copied into audit metadata.
- Queue and order responses expose only the MRN and given/family name needed for laboratory identification.

## Clinical safety boundaries

- No test definitions or clinical reference ranges are seeded. A hospital must govern and approve its own catalog.
- This module does not create reference intervals, calculate normal ranges, classify results automatically, interpret findings or generate diagnoses.
- Abnormality and critical flags are manually entered by laboratory staff; there are no automated critical thresholds or automatic notifications.
- A critical-result acknowledgement is an auditable manual action; it does not prove that a phone call or other communication channel was delivered.
- Final results cannot be edited or amended through this API. A governed addendum/amendment workflow remains future work.
- No analyzer/device integration, automated result ingestion, medication order, treatment recommendation or clinical AI action is enabled.
- No live patient or clinical test data is seeded.

## Deferred integrations

- LOINC/SNOMED mappings and FHIR DiagnosticReport/ServiceRequest/Specimen interoperability.
- Analyzer interfaces, barcode printing/scanning, laboratory information systems and device-result reconciliation.
- Multi-analyte panels, microbiology culture/susceptibility, histopathology, blood bank and point-of-care testing.
- Approved context-specific reference intervals, result interpretation and jurisdiction-specific critical thresholds.
- Specimen transport tracking, billing/insurance integration and external laboratory referral workflows.
- Credential verification against the relevant professional regulator and laboratory accreditation evidence.

All catalog governance, role boundaries, order assignment, specimen lifecycle, result integrity, two-person verification, critical acknowledgement, cancellation, tenant isolation and audit checks are in the Phase 5 Test Register. Tests have not been executed for this milestone.
