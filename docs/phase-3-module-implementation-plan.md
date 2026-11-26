# Phase 3 — Hospital modules implementation plan

## Objective

Build the 40 hospital modules on the shared Phase 1 backend and central Phase 2 AI platform. Modules are domain-specific workflows, not independent AI systems. Each calls central AI capabilities only through the approved API.

## Shared module engineering standard

Every module milestone must include:
1. Domain models and explicit Alembic migration.
2. Pydantic request/response schemas.
3. Versioned API routes and service layer.
4. Hospital RLS and department/role authorization.
5. Consent, purpose limitation and audit where patient information is involved.
6. Clear workflow states, validation and error handling.
7. API contract documentation and UI page/role requirements.
8. Phase 5 test cases added to `docs/TEST_REGISTER_PHASE_5.md`.
9. No live patient data, autonomous clinical action or clinical AI activation.
10. Branch, commit, PR, mergeability inspection, merge and main SHA verification before the next milestone.

## Module implementation order

| # | Module |
|---:|---|
| 1 | Patient Registration & Management |
| 2 | OPD |
| 3 | Nursing |
| 4 | Inpatient & Ward Management |
| 5 | Emergency & Trauma |
| 6 | ICU |
| 7 | Surgery & Theatre |
| 8 | Maternity & Newborn Care |
| 9 | Pediatrics & Child Health |
| 10 | Laboratory & Diagnostics |
| 11 | Radiology & Medical Imaging |
| 12 | Pharmacy & Medication Management |
| 13 | Billing & Finance |
| 14 | Insurance & Claims (Kenya SHA and private insurance) |
| 15 | Human Resources |
| 16 | Procurement & Supply Chain |
| 17 | Inventory & Asset Management |
| 18 | Facilities & Maintenance |
| 19 | Ambulance & Transport |
| 20 | Mortuary & Pathology |
| 21 | Hospital Administration Console |
| 22 | Patient Portal |
| 23 | Doctor & Medical Staff Portal |
| 24 | Staff Management & Scheduling |
| 25 | Medical Records & Health Information |
| 26 | Telemedicine & Remote Care |
| 27 | Communication & Notifications |
| 28 | Quality Assurance & Patient Safety |
| 29 | Compliance & Security Management |
| 30 | Reports & Hospital Analytics |
| 31 | AI Medical Assistant |
| 32 | AI Diagnostic Support |
| 33 | AI Laboratory Assistant |
| 34 | AI Radiology Assistant |
| 35 | AI Pharmacy Assistant |
| 36 | AI Patient Assistant |
| 37 | AI Hospital Analytics |
| 38 | AI Voice Assistant |
| 39 | AI Medical Knowledge Base |
| 40 | AI Workflow Automation |

## Dependencies and boundaries

- Patient Registration & Management is the foundation for encounters and later clinical workflows.
- OPD, Nursing, Inpatient, Emergency, ICU, Theatre, Maternity and Pediatrics share patient identity but retain department-specific authorization and workflows.
- Laboratory, Radiology and Pharmacy consume authorized orders and return verified results/dispensing events.
- Billing and Insurance are separate financial domains; patient-care roles do not receive unrestricted finance access.
- HR, procurement, inventory and facilities are operational domains with their own least-privilege boundaries.
- Patient, doctor, staff and administration portals are role-specific views over shared domain APIs.
- AI assistant modules are workflow clients of the central AI API; they do not host separate models, knowledge stores or bypass release gates.
- HIE, FHIR, SHA, private insurers, messaging, payment and device integrations are implemented against real partner specifications in the integration phase.

## Implementation progress

| Module | Milestone | Status | Pull request |
|---|---|---|---|
| Patient Registration & Management | Phase 3.1 | Implemented; Phase 5 verification pending | PR #27 (merged) |
| OPD | Phase 3.2 | Implemented; Phase 5 verification pending | PR #28 (merged) |
| Nursing | Phase 3.3 | Implemented; Phase 5 verification pending | PR #29 (merged) |
| Inpatient & Ward Management | Phase 3.4 | Implemented; Phase 5 verification pending | PR #30 (merged) |
| Emergency & Trauma | Phase 3.5 | Implemented; Phase 5 verification pending | PR #31 (merged) |
| ICU | Phase 3.6 | Implemented; Phase 5 verification pending | PR #32 (merged) |
| Surgery & Theatre | Phase 3.7 | Implemented; Phase 5 verification pending | PR #33 (merged) |
| Maternity & Newborn Care | Phase 3.8 | Implemented; Phase 5 verification pending | PR #34 (merged) |
| Pediatrics & Child Health | Phase 3.9 | Implemented; Phase 5 verification pending | PR #35 (merged) |
| Laboratory & Diagnostics | Phase 3.10 | Implemented; Phase 5 verification pending | PR #36 (merged) |
| Radiology & Medical Imaging | Phase 3.11 | Implemented; Phase 5 verification pending | PR #37 (merged) |
| Pharmacy & Medication Management | Phase 3.12 | Implemented; Phase 5 verification pending | PR #38 (merged) |
| Billing & Finance | Phase 3.13 | Implemented; Phase 5 verification pending | PR #39 (merged) |
| Insurance & Claims | Phase 3.14 | Implemented; Phase 5 verification pending | PR #40 (merged) |
| Human Resources | Phase 3.15 | Implemented; Phase 5 verification pending | PR #41 (merged) |
| Procurement & Supply Chain | Phase 3.16 | Implemented; Phase 5 verification pending | PR #42 (merged) |
| Inventory & Asset Management | Phase 3.17 | Implemented; Phase 5 verification pending | PR #43 (merged) |
| Facilities & Maintenance | Phase 3.18 | Implemented; Phase 5 verification pending | PR #44 (merged) |
| Ambulance & Transport | Phase 3.19 | Implemented; Phase 5 verification pending | PR #45 (merged) |
| Mortuary & Pathology | Phase 3.20 | Implemented; Phase 5 verification pending | PR #46 (merged) |
| Hospital Administration Console | Phase 3.21 | Implemented; Phase 5 verification pending | PR #48 (merged) |
| Patient Portal | Phase 3.22 | Implemented; Phase 5 verification pending | PR #51 (merged) |
| Doctor & Medical Staff Portal | Phase 3.23 | Implemented; Phase 5 verification pending | PR #52 and hardening PR #54 (merged) |
| Staff Management & Scheduling | Phase 3.24 | Implemented; Phase 5 verification pending | PR #56 (merged) |
| Medical Records & Health Information | Phase 3.25 | Implemented; Phase 5 verification pending | PR #57 (merged) |
| Telemedicine & Remote Care | Phase 3.26 | Implemented; Phase 5 verification pending | PR #58 (merged) |
| Communication & Notifications | Phase 3.27 | Implemented; Phase 5 verification pending | PRs #59–#62 (merged) |
| Quality Assurance & Patient Safety | Phase 3.28 | Implemented; Phase 5 verification pending | PRs #63–#64 (merged) |
| Compliance & Security Management | Phase 3.29 | Implemented; Phase 5 verification pending | PRs #65–#67 (merged) |
| Reports & Hospital Analytics | Phase 3.30 | Implemented; Phase 5 verification pending | PR #68 (merged) |
| AI Medical Assistant | Phase 3.31 | Implemented; Phase 5 verification pending | PR #69 (merged) |
| AI Diagnostic Support | Phase 3.32 | In progress | — |

Patient Registration & Management extends the Phase 1 patient foundation with governed duplicate review, identity/document metadata, contact and next-of-kin details, consent/lawful-basis recording, patient status and audit history. Automatic patient merging is prohibited.

OPD provides registration, queue, arrival, manual triage, assigned clinician consultation, diagnosis recording and disposition. Nursing provides assignment-scoped assessments, observations, signed notes and care plans. Inpatient & Ward Management adds ward/bed inventory, admission requests and acceptance, bed assignment, care-team assignment and clinician-led discharge. Emergency & Trauma adds arrival registration, manual triage/reassessment, assigned clinician treatment, care events, signed notes and disposition. ICU adds assigned ICU stays, observations, care events, signed progress notes and stepdown requests. Surgery & Theatre adds theatre scheduling, assigned surgical teams, safety checklist gates, anesthesia documentation, operative events and recovery completion. Maternity & Newborn Care adds pregnancy episodes, antenatal visits, labor observations, delivery and cesarean linkage, newborn records, postpartum monitoring and pregnancy-ending documentation. Pediatrics & Child Health adds assigned encounter-scoped pediatric records, append-only growth observations, manually documented developmental screenings, immunization history provenance and signed pediatric notes. Laboratory & Diagnostics adds a two-person-approved test catalog, assigned clinician orders, specimen accessioning and lifecycle tracking, preliminary/final results, manual critical flags and clinician acknowledgement. Radiology & Medical Imaging adds an approved procedure catalog, assigned imaging orders, accessioned studies, preliminary/final reports and manual critical-finding acknowledgement. Pharmacy & Medication Management adds a governed medication catalog, assigned prescriptions, pharmacist review events, partial/full dispensing and cancellation controls. Billing & Finance adds a governed service catalog, encounter invoices, immutable line items, partial/full payment records, independent payment confirmation and voiding controls. Insurance & Claims adds an approved hospital insurer catalog, patient coverage records, manual verification references, invoice-linked claim submission, recorded adjudication, payment tracking and append-only claim events; live payer integrations remain in Phase 4. Human Resources adds hospital-scoped employee profiles, department/manager links, manually reviewed professional credentials and employee leave requests with independent HR approval; payroll, biometrics, shift rosters and live regulator checks are excluded. Procurement & Supply Chain adds hospital vendor records, departmental purchase requisitions, independent approval, approved-requisition conversion to purchase orders, server-calculated order totals and independent PO issuance; goods receipt and stock management remain in Module 17. All modules remain subject to the Phase 5 test campaign and clinical/security release gates.


Inventory & Asset Management adds a hospital-scoped item catalog, warehouses, purchase-order-backed goods receipts with quantity/lot/serial metadata, transactional stock balances and an append-only movement ledger, plus individually tagged equipment and fixed-asset records. Posting receipts validates cumulative quantities against issued purchase orders and updates purchase-order receipt status. Stock issue, reservation, transfer, valuation, depreciation and maintenance work orders remain outside this milestone. Phase 5 verification is pending.


Facilities & Maintenance adds a hospital-scoped facility location hierarchy, asset-linked maintenance requests, independent approval/rejection, technician assignment, work start/completion and an append-only event history. Preventive maintenance, spare-parts consumption, vendor dispatch, calibration certification and building-system integrations remain excluded. Phase 5 verification is pending.




Ambulance & Transport adds consent-gated interfacility transfer requests, minimized receiving-hospital offers for bed acceptance/rejection, ambulance fleet records and status management, driver/crew assignment, dispatch, manually recorded location updates, receiving arrival confirmation and origin fleet release. Receiving hospitals do not receive patient/encounter identifiers or clinical details through this module. Actual inpatient bed reservation, patient-record exchange and live GPS/dispatch integrations remain separate workflows or Phase 4 integrations. Phase 5 verification is pending.


Mortuary & Pathology adds hospital-scoped mortuary intake, body identification and storage movements, legal holds, independently verified release authority, personal-effects custody and controlled release. Pathology adds case registration, autopsy/forensic authority verification, specimen accession and processing states, assigned pathologists, versioned reports and immutable signed finals. It does not determine cause of death, issue death certificates, provide AI pathology interpretation or establish legal sufficiency; external statutory and registry integrations remain out of scope. Phase 5 verification is pending.


Hospital Administration Console adds hospital profile and branding, operational settings, weekly operating hours, department hierarchy/manager/contact governance, aggregate administration dashboard and immutable administrative event history. Appointment booking, patient self-registration and public-directory flags remain configuration values until Phase 4 connects enforcement to their respective workflows. Record sharing remains request-based and consent-gated.


Patient Portal adds staff-verified links between existing user accounts and patient records, scoped and expiring proxy access, patient-scoped record views for encounters, finalized laboratory results, medications, invoices and consents, plus immutable access-event logging. Account signup/OTP, MFA challenge, appointments, secure messaging, payments and cross-hospital exchange remain Phase 4 or later integrations.


Doctor & Medical Staff Portal adds independently verified clinical staff profiles, scoped patient care-team assignments, a role-aware patient overview and an assigned work queue. Existing clinical endpoints still require Phase 4 integration of care-team authorization before these assignments become a universal patient access boundary.


Phase 3.23 access hardening: suspending clinical credentials now revokes active care-team assignments; patient-linked task reads and updates require current assignment and task-specific scope; future-start assignments are excluded from active worklists and dashboard counts. Phase 5 verification remains pending.


Phase 3.24 adds hospital-scoped shift templates and employee assignments, conflict detection against overlapping shifts and approved leave, employee-initiated shift swaps with target acceptance and independent manager approval, manual attendance check-in/check-out with manager review, department-scoped roster access, dashboard counts and an append-only schedule event ledger. HR leave approval now rejects dates that overlap scheduled or confirmed shifts. Automated verification remains deferred to Phase 5.


Phase 3.25 introduces a hospital-scoped longitudinal document index using encrypted-vault references and checksum metadata, independent document verification and immutable version history, consent-gated release-of-information requests, and non-destructive record amendment/addendum workflows. Existing department modules remain authoritative for their clinical records; automatic document publication and vault object verification are Phase 4 integrations. Patient/proxy self-service release remains gated on verified portal identity. Phase 5 verification is pending.


Phase 3.26 adds telemedicine scheduling and session lifecycle, active verified provider and roster validation, purpose-specific telemedicine consent, patient identity/privacy/emergency readiness checks, care-team-gated session start, encounter creation, immutable signed consultation notes, and safe cancellation/no-show/closure. Live video transport, patient self-service booking, secure vault operations, notifications and department order integrations are Phase 4 work. Phase 5 verification is pending.


Phase 3.27 scope: hospital-scoped communication preferences and consent-aware notification intents; role- and department-scoped recipient resolution; template/version governance; queued delivery with idempotency, retry scheduling and terminal failure states; provider-neutral delivery attempts and immutable event history. Notifications must contain minimum-necessary content, avoid clinical details and direct identifiers by default, respect quiet hours and channel opt-outs, and never claim delivery until a provider acknowledgement is recorded. SMS, email, push and in-app provider execution, patient contact verification, appointment integrations and external messaging credentials are Phase 4 integrations. No clinical urgency routing or emergency dispatch is introduced by this module.


Phase 3.27 hardening follow-up: recipient-scoped notification event-history endpoints, idempotency-key payload collision protection, and patient portal link expiry revalidation were merged in PR #71. Phase 5 verification remains pending.
