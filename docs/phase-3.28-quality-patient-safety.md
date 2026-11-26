# Phase 3.28 — Quality Assurance & Patient Safety

## Objective
Provide a hospital-wide, auditable quality and patient-safety management module. It supports incident reporting, near-miss capture, structured review, corrective and preventive action (CAPA), safety rounds, quality indicators and governance oversight. It is an operational quality system, not a clinical decision engine.

## Functional scope
- Patient safety incident and near-miss reporting with confidential reporter identity handling.
- Incident classification, severity, harm level, location, department and event timeline.
- Immediate containment actions and escalation workflow for designated safety officers.
- Structured investigation, contributing-factor analysis and review findings.
- CAPA plans with accountable owners, due dates, evidence references, effectiveness checks and closure approval.
- Safety rounds and inspection checklists with tracked findings.
- Quality indicators with versioned definitions, denominator/numerator metadata, reporting periods and data provenance.
- Department quality dashboards and hospital governance dashboard.
- Restricted safety committee access, role-scoped workflows and immutable audit history.

## Safety and privacy invariants
- Hospital RLS and composite tenant keys for every tenant-owned record.
- Reporter identity is confidential by default and visible only to authorized safety officers/investigators; no anonymous claim unless reporter identity is actually withheld.
- Clinical record content is not copied into incident narratives by default; reference existing encounter/record IDs with least-necessary context.
- Incident severity and harm classification are recorded facts/reviewer judgments, not generated diagnoses.
- Serious events follow configured human escalation pathways; no automated emergency dispatch or clinical intervention.
- CAPA closure requires documented effectiveness review by an authorized reviewer distinct from the action owner.
- Quality metrics preserve definition version, source, period, numerator, denominator and calculation metadata; no fabricated rates.
- All status transitions, access to confidential reports, investigation decisions and CAPA approvals are auditable.

## Initial workflow
Report → triage/classify → assign safety officer → contain → investigate → CAPA plan → evidence/effectiveness review → authorized closure. Near misses may be reviewed without a harm classification.

## Phase 3 / Phase 4 boundary
Phase 3 implements database models, authorization, APIs, workflows, dashboards and manual data entry. Phase 4 connects clinical modules as event sources, external accreditation/reporting standards, national safety reporting portals and hospital BI systems.

## Verification
All security, workflow, privacy, audit, metric integrity, CAPA and tenant-isolation scenarios are recorded in docs/TEST_REGISTER_PHASE_5.md. Backend tests remain deferred to Phase 5.


## Implemented foundation
- Safety incident reporting with confidential reporter identity by default and optional patient/encounter linkage.
- Safety officer and department manager visibility rules.
- Triage classification, investigation assignment, findings submission and independent review.
- Corrective/preventive actions with evidence vault references and independent effectiveness review.
- Incident closure gate requiring an approved investigation and all CAPA actions completed.
- Department-scoped and hospital-wide aggregate dashboards, plus personal CAPA worklist.
- Migration 0047_quality_patient_safety creates tenant-isolated tables and append-only incident event history.

## API surface
- POST/GET /api/v1/quality/incidents
- GET /api/v1/quality/incidents/{incident_id}
- POST /api/v1/quality/incidents/{incident_id}/triage
- POST /api/v1/quality/incidents/{incident_id}/investigation
- PATCH /api/v1/quality/investigations/{investigation_id}
- POST /api/v1/quality/investigations/{investigation_id}/review
- POST /api/v1/quality/incidents/{incident_id}/capa
- POST /api/v1/quality/capa/{action_id}/evidence
- POST /api/v1/quality/capa/{action_id}/effectiveness-review
- POST /api/v1/quality/incidents/{incident_id}/close
- GET /api/v1/quality/dashboard
- GET /api/v1/quality/my-capa

Safety rounds, inspection checklists, indicator definitions/measurements and external accreditation reporting remain follow-on work within Phase 3.28. Backend tests remain deferred to Phase 5.
