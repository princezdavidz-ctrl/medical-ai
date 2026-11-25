# Phase 3.15 — Human Resources

## Scope delivered

The HR module manages hospital-scoped staff records and administrative workflows. It does not replace the identity/authentication service: every employee profile links to an existing active platform user.

### Employee directory
- Create one employee profile per user per hospital.
- Store employee number, department, job title, employment type/status, start/end dates and optional manager.
- Department and manager references must belong to the same hospital.
- Only HR administrators can create profiles or change employment status.
- HR staff can view the hospital's directory; ordinary staff do not receive directory-wide access.

### Professional credentials
- Record credential type/number, issuing body, validity dates and an opaque evidence reference.
- Credentials start as reported and require an independent HR administrator decision.
- Verification attribution and timestamp are recorded.
- This is a manual evidence-review workflow, not a live check against KMPDC, Nursing Council, Pharmacy and Poisons Board or another regulator.

### Leave requests
- An employee with an active HR profile can submit a dated leave request.
- HR administrators can approve or reject requests, with decision actor/time and reason recorded.
- Requesters cannot approve their own leave.
- The module records leave decisions; it does not automatically alter clinical rosters, payroll, time clocks or patient-care assignments.

## API surface

- POST /api/v1/hr/employees
- GET /api/v1/hr/employees
- PATCH /api/v1/hr/employees/{employee_id}/status
- POST /api/v1/hr/employees/{employee_id}/credentials
- POST /api/v1/hr/credentials/{credential_id}/decision
- POST /api/v1/hr/leave-requests
- GET /api/v1/hr/leave-requests
- POST /api/v1/hr/leave-requests/{request_id}/decision

## Authorization

- HR administrators: hr_manager, hr_director, hospital_admin.
- HR staff: HR administrators plus hr_officer, hr_assistant.
- Credential decisions are restricted to HR administrators.
- Employee self-service is limited to that employee's own leave requests.
- All records are hospital-scoped, protected by PostgreSQL RLS and composite hospital-to-department/employee foreign keys.
- Sensitive credential numbers and evidence references are not copied into audit metadata.

## Explicit exclusions

- Payroll, tax, pension, benefits, salary payments and expense reimbursements.
- Shift/rota generation, attendance clocks, biometric collection or face recognition.
- Automated licensing checks, regulator integrations, credential authenticity guarantees or external document storage.
- Recruitment applicant tracking, performance reviews, disciplinary proceedings and training/LMS.
- Automatic leave balance calculation or automatic changes to staffing/clinical assignments.

These workflows may be added in later modules or Phase 4 integrations. Validation is deferred to Phase 5; no backend tests were run for this milestone.
