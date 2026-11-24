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
| Surgery & Theatre | Phase 3.7 | In implementation | Current branch |

Patient Registration & Management extends the Phase 1 patient foundation with governed duplicate review, identity/document metadata, contact and next-of-kin details, consent/lawful-basis recording, patient status and audit history. Automatic patient merging is prohibited.

OPD provides registration, queue, arrival, manual triage, assigned clinician consultation, diagnosis recording and disposition. Nursing provides assignment-scoped assessments, observations, signed notes and care plans. Inpatient & Ward Management adds ward/bed inventory, admission requests and acceptance, bed assignment, care-team assignment and clinician-led discharge. Emergency & Trauma adds arrival registration, manual triage/reassessment, assigned clinician treatment, care events, signed notes and disposition. ICU adds assigned ICU stays, observations, care events, signed progress notes and stepdown requests. Surgery & Theatre adds theatre scheduling, assigned surgical teams, safety checklist gates, anesthesia documentation, operative events and recovery completion. All modules remain subject to the Phase 5 test campaign and clinical/security release gates.
