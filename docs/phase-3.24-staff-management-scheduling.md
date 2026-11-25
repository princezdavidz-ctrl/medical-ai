# Phase 3.24 — Staff Management & Scheduling

## Purpose

Provide hospital-scoped workforce scheduling workflows built on the employee records and leave requests from Phase 3.15 Human Resources. This module is operational scheduling only; it does not replace HR employment records or payroll.

## Capabilities

- Department-aware shift templates with day, evening, night, on-call and other categories.
- Timezone-aware employee shift assignments linked to active HR employee profiles, active hospital memberships, active user accounts, departments and templates.
- Conflict detection for overlapping scheduled/confirmed shifts and approved leave. Shifts are limited to a positive duration of at most 24 hours; overnight shifts are supported.
- Employee shift views and manager roster views with department-scoped access for department heads and nurse managers.
- Shift swap requests initiated by the assigned employee, accepted/declined by the proposed replacement, and independently approved/rejected by a roster manager. The original assignment changes only after manager approval.
- Requester cancellation before final manager decision, plus a database uniqueness rule allowing only one open swap request per shift.
- Manual attendance check-in/check-out, one record per shift, and independent manager approval/rejection. Rejected attendance can be corrected and resubmitted.
- Staff and manager dashboard aggregates.
- Hospital-scoped append-only schedule event ledger and standard audit events.

## API

Base prefix: `/api/v1/staff-scheduling`

| Method | Path | Purpose |
|---|---|---|
| POST | `/templates` | Create a shift template |
| GET | `/templates` | List templates visible to the current department/employee |
| PATCH | `/templates/{template_id}` | Update/deactivate a template |
| POST | `/shifts` | Assign an employee to a shift |
| GET | `/my-shifts` | List the current employee's shifts |
| GET | `/shifts` | Manager roster with optional date/department filters |
| PATCH | `/shifts/{shift_id}` | Update, confirm or cancel a shift |
| POST | `/shifts/{shift_id}/swap-requests` | Request a shift swap |
| GET | `/swap-requests` | List own or manager-visible swap requests |
| POST | `/swap-requests/{request_id}/cancel` | Cancel own pending/accepted request |
| POST | `/swap-requests/{request_id}/respond` | Target employee accepts or declines |
| POST | `/swap-requests/{request_id}/decision` | Manager approves/rejects accepted swap |
| POST | `/shifts/{shift_id}/check-in` | Record manual check-in |
| POST | `/shifts/{shift_id}/check-out` | Submit attendance |
| POST | `/attendance/{attendance_id}/decision` | Manager approves/rejects attendance |
| POST | `/attendance/{attendance_id}/resubmit` | Correct and resubmit rejected attendance |
| GET | `/dashboard` | Role-scoped scheduling counts |

## Authorization and integrity

- Every record is hospital-scoped and protected by PostgreSQL row-level security.
- Department heads and nurse managers are limited to their active employee department. Hospital and HR roster managers have hospital-wide scope according to their role.
- Assignments require an active employee profile, active hospital membership and active user account.
- Assignment and swap approval re-check employment, department, leave and overlapping shifts.
- Employee-row locking serializes assignment/swap checks; a partial unique index prevents multiple open swap requests for one shift.
- Attendance is manual only in this phase. Biometric, GPS, payroll and external clock integrations are not included.
- Schedule events are append-only at database level. Standard audit events record sensitive workflow actions.

## HR integration

Shift assignment rejects overlap with approved leave. Conversely, HR leave approval now rejects a request when it overlaps a scheduled or confirmed shift. This prevents either workflow from silently creating a conflicting schedule.

## Exclusions

Payroll, overtime calculation, wage rules, biometric attendance, GPS/geofencing, staff credential verification, recruitment, annual leave accrual calculations, automated roster optimization, union/collective agreement rules, notifications and external calendar integrations are excluded. These remain separate HR, integration or future scheduling capabilities.

## Verification

No backend tests were run during module development, per project direction. All migration, authorization, concurrency, workflow and regression scenarios are recorded in `docs/TEST_REGISTER_PHASE_5.md` for Phase 5.
