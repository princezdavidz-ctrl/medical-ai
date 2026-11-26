# Phase 3.29 — Compliance & Security Management

## Objective
Provide hospital-level governance workflows for policies, compliance controls, security incidents, risk assessment and periodic access reviews. This module manages evidence and accountability; it does not certify legal or regulatory compliance automatically.

## Functional scope
- Versioned policies, publication, effective dates and staff acknowledgement tracking.
- Compliance control register with owner, framework mapping, applicability, evidence references and assessment status.
- Periodic control assessments with reviewer sign-off and remediation actions.
- Security/privacy incident reporting, severity classification, containment, investigation and breach assessment.
- Security incident event timeline with immutable audit history.
- Risk register with likelihood, impact, mitigation owner, due date and residual risk.
- Role and department access review campaigns, reviewer assignment, attestations and revocation recommendations.
- Retention schedules, legal hold references and documented disposition approvals.
- Hospital compliance dashboard with overdue acknowledgements, open risks, unresolved incidents and pending reviews.

## Security and privacy invariants
- Hospital RLS and tenant-scoped composite foreign keys on every tenant-owned table.
- Confidential security reports are restricted to designated security/privacy officers; reporter identity is not exposed to ordinary staff.
- Evidence is stored by vault reference and checksum/metadata, never as public URLs or credentials.
- Policy versions are immutable after publication; corrections require a new version.
- Access review does not automatically revoke access; a human approver must confirm each change and record the outcome.
- Security incidents and event histories are auditable; incident narratives and secrets are excluded from generic audit metadata.
- Risk scores are transparent, formula-based and not represented as legal determinations.
- Retention/deletion workflows respect active legal holds and require authorized approval.

## Phase 3 / Phase 4 boundary
Phase 3 implements local registers, workflows, role enforcement, evidence references and dashboards. Phase 4 connects external identity providers, security monitoring/SIEM, national breach-reporting channels, accreditation frameworks and automated data-retention jobs.

## Verification
All access, confidentiality, tenant isolation, approval, immutability, evidence, retention and audit scenarios are registered in docs/TEST_REGISTER_PHASE_5.md. Backend tests remain deferred to Phase 5.


## Implemented foundation
- Versioned compliance policies stored as private vault references, with independent publication approval and effective dates.
- Append-only policy acknowledgements for active hospital members and acknowledgement reporting for compliance officers.
- Confidential security incident reporting, role-restricted triage, same-hospital investigator assignment, containment, breach assessment and controlled closure.
- Risk register with likelihood/impact scoring, residual risk scoring, accountable owners and independent review.
- Hospital-scoped compliance dashboard aggregating security incident and risk states.
- Migration 0049_compliance_security adds five tenant-isolated tables, RLS, composite membership references and immutable policy/event/acknowledgement controls.

## API surface
- POST/GET /api/v1/compliance/policies
- POST /api/v1/compliance/policies/{policy_id}/publish
- POST /api/v1/compliance/policies/{policy_id}/acknowledge
- GET /api/v1/compliance/policies/{policy_id}/acknowledgements
- POST/GET /api/v1/compliance/security-incidents
- POST /api/v1/compliance/security-incidents/{incident_id}/triage
- POST /api/v1/compliance/security-incidents/{incident_id}/assign
- PATCH /api/v1/compliance/security-incidents/{incident_id}
- POST /api/v1/compliance/security-incidents/{incident_id}/close
- POST/GET /api/v1/compliance/risks
- POST /api/v1/compliance/risks/{risk_id}/review
- GET /api/v1/compliance/dashboard

Compliance control register, access review campaigns, retention schedules/legal holds and external breach reporting remain follow-on work within Phase 3.29.
