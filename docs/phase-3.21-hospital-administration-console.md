# Phase 3.21 — Hospital Administration Console

## Scope
A hospital-scoped administrative control plane for operational overview, facility settings, department directory governance, role catalog visibility and staff membership approval/suspension. It does not replace department dashboards or grant platform-wide cross-hospital administration.

## Authorization and tenant boundary
- Only active memberships holding `hospital_admin` or `hospital_director` can use these endpoints.
- All reads and writes are scoped to the hospital in the authenticated context.
- Membership activation requires a role defined by the same hospital and, when supplied, an active department from that hospital.
- A user cannot change their own membership through this workflow. The final active hospital administrator cannot be suspended.
- Role creation and privilege-definition editing are excluded; the console assigns only existing hospital roles. Custom role permission matrices require a separate governed authorization design.

## API
- `GET /api/v1/hospital-admin/overview` — aggregate hospital, department, membership, patient and encounter counts; no patient-level records.
- `GET /api/v1/hospital-admin/settings`
- `PUT /api/v1/hospital-admin/settings` — contact/address, timezone, locale, currency and country.
- `GET /api/v1/hospital-admin/departments`
- `POST /api/v1/hospital-admin/departments`
- `PATCH /api/v1/hospital-admin/departments/{department_id}`
- `GET /api/v1/hospital-admin/roles`
- `GET /api/v1/hospital-admin/memberships?status_filter=pending`
- `POST /api/v1/hospital-admin/memberships/{membership_id}/decision` — activate, reject or suspend.

## Controls
1. Department codes are unique per hospital. A department with active staff cannot be deactivated.
2. Membership role and department assignments are constrained to the same hospital at database level using composite foreign keys.
3. Membership activation is an explicit admin decision; it does not automatically create a user or bypass authentication.
4. Self-modification is denied. Suspending the final active hospital administrator is denied.
5. Dashboard metrics are aggregate counts only; no clinical narrative, MRN or patient identifiers are returned.
6. Every mutation emits an audit event. Hospital settings are protected by hospital RLS.

## Boundaries
No cross-hospital platform super-admin, subscription billing, staff recruitment/payroll, custom role-permission editor, clinical workflow overrides, patient-record browsing, audit-log export, security incident response or external identity-provider provisioning. Existing department-specific workflows remain authoritative for clinical and operational actions.

## Phase 5 verification
Tests are deferred to the central Phase 5 campaign. Verify tenant RLS/composite FKs, administrator authorization, last-admin protection, membership approval/rejection/suspension, department lifecycle, settings validation, aggregate metric privacy and audit attribution.
