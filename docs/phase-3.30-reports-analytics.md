# Phase 3.30 — Reports & Hospital Analytics

## Objective
Provide trusted, role-scoped hospital reporting and operational analytics across clinical, administrative, financial and quality domains. Reports must preserve source provenance and avoid exposing data outside the viewer's hospital, department, role and patient-care authorization.

## Functional scope
- Report catalog with versioned definitions, owners, data domains, refresh cadence and access classification.
- Parameterized report runs with date ranges, department scope and approved filters.
- Operational dashboards for patient flow, bed occupancy, emergency activity, theatre utilization, laboratory turnaround, pharmacy dispensing and staffing.
- Financial and administrative dashboards for billing, claims, procurement, inventory and facilities, with finance/operations role restrictions.
- Quality, safety, compliance and security metrics from their governed modules.
- Export jobs for CSV/PDF with access checks, expiration and audit trail.
- Scheduled report definitions and delivery preferences; external delivery is Phase 4.
- Data provenance, calculation version, generation timestamp and completeness indicators.
- Aggregate-first reporting; row-level drill-down reuses source module authorization and patient-care assignment checks.

## Security and integrity invariants
- Hospital RLS and least-privilege report catalog permissions.
- Department managers see only their department's permitted metrics; finance roles see finance data; clinical roles do not receive unrestricted financial detail.
- Patient-level drill-down must re-run source module authorization; analytics permissions never grant clinical record access.
- Exports are time-limited, private vault references, watermarked where required and audited.
- No report may silently infer missing values as zero; completeness and missingness are explicit.
- Every metric records its definition/version, source module, aggregation period and calculation timestamp.
- Small-cell suppression and privacy thresholds apply to sensitive aggregate cohorts where required.
- Reports are informational and do not make clinical decisions or replace clinician review.

## Phase 3 / Phase 4 boundary
Phase 3 implements report definitions, governed aggregate queries, dashboards, audit and export-job metadata. Phase 4 connects warehouse/BI infrastructure, scheduled execution workers, external delivery, national reporting and cross-module event pipelines.

## Verification
All authorization, metric integrity, data provenance, export privacy, tenant isolation and performance scenarios are recorded in docs/TEST_REGISTER_PHASE_5.md. Backend tests remain deferred to Phase 5.


## Implemented foundation
- Versioned report definitions use a fixed, whitelisted report-key set; definitions cannot execute caller-supplied SQL.
- Independent publication approval and role/domain-specific report authorization.
- Synchronous aggregate reports for inpatient flow, bed occupancy, emergency volume, billing summaries, quality/safety and compliance overview.
- Department managers are automatically constrained to their assigned department; finance and compliance reports require dedicated role scopes.
- Small-cell suppression threshold of five prevents low-count aggregate disclosure; billing amounts are suppressed with their small-cell count.
- Report runs preserve filters, report definition version, calculation version, generation time and a 24-hour expiry.
- CSV/PDF export requests create private export-job metadata only; actual file generation, vault storage and scheduled delivery are Phase 4.
- Migration 0052_hospital_reporting creates the report catalog, run history and export-job tables with RLS and immutable published definitions.

## API surface
- POST /api/v1/reports/definitions
- POST /api/v1/reports/definitions/{definition_id}/publish
- GET /api/v1/reports/catalog
- POST /api/v1/reports/definitions/{definition_id}/run
- GET /api/v1/reports/runs
- POST /api/v1/reports/runs/{run_id}/exports
