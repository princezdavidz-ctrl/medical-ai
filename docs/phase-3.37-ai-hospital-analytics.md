# Phase 3.37 — AI Hospital Analytics

## Objective
Provide evidence-grounded operational analysis over existing governed hospital reports without duplicating the Phase 3.30 reporting engine or exposing patient-level records.

## API
- POST /api/v1/ai/operations/insights
- Request: report_run_id and a management question.
- Source: one completed, unexpired report run and its published report definition.
- Output: advisory insight, evidence citations, report provenance, model/prompt metadata and explicit management-review/action/forecasting flags.

## Security and data boundaries
- Reuses the source report's hospital, role, domain and department authorization.
- Department heads and nurse managers are restricted to a report snapshot for their active department.
- Finance and compliance report domains retain specialist role checks.
- Supplies only the report's aggregate result summary, filters, source versions and timestamps; it does not query patient rows or clinical narratives.
- Forces local-provider routing even in hybrid mode. Local runtime failure returns an explicit unavailable response; hosted transfer is never attempted.
- Capability is separately allow-listed and remains disabled unless approved by configuration.
- Only approved, current operational guidelines and policies can ground recommendations.

## Explicit exclusions
- No patient-level drill-down, diagnosis or treatment support.
- No automatic bed assignment, staffing changes, triage changes, patient prioritization, spending approval or workflow execution.
- No predictive bed occupancy, waiting-time, demand or staffing forecasts until a validated model and dataset are separately approved.
- No schema migration; existing report run and knowledge provenance are reused.

## Verification
All authorization, data-minimization, evidence, offline-routing, audit and action-boundary scenarios are listed in docs/TEST_REGISTER_PHASE_5.md. Backend tests remain deferred to Phase 5.
