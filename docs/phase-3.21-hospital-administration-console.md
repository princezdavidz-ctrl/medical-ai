# Phase 3.21 — Hospital Administration Console

## Scope
Hospital administrator workspace APIs for institutional profile and branding, operating configuration, weekly operating hours, department hierarchy and contact/manager metadata, operational dashboard summaries and immutable administration events.

## Authorization
All endpoints require an active hospital membership with `hospital_admin` or `hospital_owner`. Department managers must be active members of the same hospital with `department_manager`, `department_head` or `hospital_admin` role. Every profile, settings, operating-hour and event row is hospital-scoped and protected by RLS. Department rows retain the existing hospital RLS policy and gain tenant-safe parent-department constraints.

## API
- `GET/PUT /api/v1/hospital-admin/profile`
- `GET/PUT /api/v1/hospital-admin/settings`
- `GET/PUT /api/v1/hospital-admin/operating-hours`
- `GET /api/v1/hospital-admin/departments`
- `POST /api/v1/hospital-admin/departments`
- `PATCH /api/v1/hospital-admin/departments/{department_id}`
- `GET /api/v1/hospital-admin/dashboard`
- `GET /api/v1/hospital-admin/events`

## Configuration
- Hospital profile: legal/display names, facility category, license reference, postal address, contact details, website, country, timezone, locale, currency, brand colors and protected logo reference.
- Operational settings: appointment booking, patient self-registration, public directory, default appointment duration and advance-booking horizon.
- Operating hours: exactly one entry for each weekday (Monday=0 through Sunday=6), with closed days represented without opening/closing times.
- Department governance: same-hospital parent/child hierarchy, manager assignment, contact details, activation/deactivation and cycle prevention.
- Dashboard: aggregate counts for patients, active departments, beds, admissions, active employees, open maintenance orders and open transport requests. It does not return patient-level data.

## Department safety rules
1. Parent departments must be active and belong to the same hospital.
2. Parent updates cannot create a hierarchy cycle.
3. Department managers must have an active same-hospital membership and an approved department-management role.
4. A department cannot be deactivated while it has active staff memberships, active wards or scheduled/in-progress encounters.
5. Departments are deactivated rather than deleted, preserving historical references.

## Audit and integration boundaries
All administrative changes append an immutable hospital-admin event and a standard audit event. The appointment booking, self-registration and public-directory flags are configuration values; Phase 4 must connect them to their respective workflows before they are treated as enforcement controls. Record sharing remains request-based and consent-gated and is not configurable here. User provisioning, role/permission administration, subscriptions, payroll, billing, clinical workflows and external regulator integrations remain in their dedicated modules.

## Phase 5 verification
Automated tests are deferred. Validate tenant isolation, administrator authorization, profile validation, timezone handling, settings bounds, weekly hours replacement, department hierarchy and deactivation rules, dashboard aggregates and immutable administration events.
